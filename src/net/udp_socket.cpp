#include "hft/net/udp_socket.hpp"

#include <arpa/inet.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>

#include <cerrno>
#include <charconv>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <system_error>
#include <utility>
#include <vector>

namespace hft::net {

namespace {

[[noreturn]] void throw_errno(const std::string& what) {
  throw std::system_error(errno, std::generic_category(), what);
}

void set_int_option(int fd, int level, int name, int value, const char* what) {
  if (::setsockopt(fd, level, name, &value, sizeof value) != 0) throw_errno(what);
}

}  // namespace

Endpoint Endpoint::parse(std::string_view text) {
  const auto colon = text.rfind(':');
  if (colon == std::string_view::npos) throw std::invalid_argument("expected ip:port, got " + std::string(text));
  Endpoint ep;
  ep.ip = std::string(text.substr(0, colon));
  const auto port = text.substr(colon + 1);
  const auto [ptr, ec] = std::from_chars(port.data(), port.data() + port.size(), ep.port);
  in_addr addr{};
  if (ec != std::errc{} || ptr != port.data() + port.size() || ::inet_pton(AF_INET, ep.ip.c_str(), &addr) != 1) {
    throw std::invalid_argument("expected ip:port, got " + std::string(text));
  }
  return ep;
}

sockaddr_in Endpoint::to_sockaddr() const {
  sockaddr_in sa{};
  sa.sin_family = AF_INET;
  sa.sin_port = htons(port);  // network byte order is big-endian, like ITCH
  ::inet_pton(AF_INET, ip.c_str(), &sa.sin_addr);
  return sa;
}

bool Endpoint::is_multicast() const {
  const sockaddr_in sa = to_sockaddr();
  return (ntohl(sa.sin_addr.s_addr) >> 28) == 0xE;  // 1110xxxx: 224.0.0.0/4
}

UdpSocket UdpSocket::open_sender(int ttl, bool multicast_loopback) {
  const int fd = ::socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC, 0);
  if (fd < 0) throw_errno("socket");
  UdpSocket s(fd);
  set_int_option(fd, IPPROTO_IP, IP_MULTICAST_TTL, ttl, "IP_MULTICAST_TTL");
  set_int_option(fd, IPPROTO_IP, IP_MULTICAST_LOOP, multicast_loopback ? 1 : 0, "IP_MULTICAST_LOOP");
  return s;
}

UdpSocket UdpSocket::open_receiver(const Endpoint& ep, int rcvbuf_bytes) {
  const int fd = ::socket(AF_INET, SOCK_DGRAM | SOCK_CLOEXEC | SOCK_NONBLOCK, 0);
  if (fd < 0) throw_errno("socket");
  UdpSocket s(fd);
  // Several processes on one host may listen to the same group and port.
  set_int_option(fd, SOL_SOCKET, SO_REUSEADDR, 1, "SO_REUSEADDR");
  // A bigger buffer absorbs bursts while the thread is busy. When it
  // overflows, the kernel drops datagrams (counted in RcvbufErrors).
  set_int_option(fd, SOL_SOCKET, SO_RCVBUF, rcvbuf_bytes, "SO_RCVBUF");

  // Binding to the group address (not 0.0.0.0) filters out datagrams sent to
  // other groups that happen to use the same port.
  const sockaddr_in addr = ep.to_sockaddr();
  if (::bind(fd, reinterpret_cast<const sockaddr*>(&addr), sizeof addr) != 0) {
    throw_errno("bind " + ep.ip + ":" + std::to_string(ep.port));
  }
  if (ep.is_multicast()) {
    // Joining makes the kernel (and, via IGMP, the network switches) send
    // this group's traffic here. INADDR_ANY lets the kernel pick the
    // interface from the routing table.
    ip_mreq mreq{};
    mreq.imr_multiaddr = addr.sin_addr;
    mreq.imr_interface.s_addr = htonl(INADDR_ANY);
    if (::setsockopt(fd, IPPROTO_IP, IP_ADD_MEMBERSHIP, &mreq, sizeof mreq) != 0) {
      throw_errno("IP_ADD_MEMBERSHIP " + ep.ip);
    }
  }
  return s;
}

UdpSocket::UdpSocket(UdpSocket&& other) noexcept : fd_(std::exchange(other.fd_, -1)) {}

UdpSocket& UdpSocket::operator=(UdpSocket&& other) noexcept {
  if (this != &other) {
    if (fd_ >= 0) ::close(fd_);
    fd_ = std::exchange(other.fd_, -1);
  }
  return *this;
}

UdpSocket::~UdpSocket() {
  if (fd_ >= 0) ::close(fd_);
}

std::ptrdiff_t UdpSocket::try_recv(std::span<std::byte> buf) noexcept {
  // MSG_TRUNC: return the datagram's real length even if it was cut short.
  const ssize_t n = ::recv(fd_, buf.data(), buf.size(), MSG_DONTWAIT | MSG_TRUNC);
  if (n >= 0) return n;
  return (errno == EAGAIN || errno == EWOULDBLOCK) ? 0 : -1;
}

std::ptrdiff_t UdpSocket::recv_blocking(std::span<std::byte> buf) noexcept {
  // The socket is non-blocking, so wait in poll() for it to become readable.
  // That puts the thread to sleep in the kernel until a datagram arrives,
  // which is exactly the wake-up cost being measured.
  while (true) {
    const ssize_t n = ::recv(fd_, buf.data(), buf.size(), MSG_TRUNC);
    if (n >= 0) return n;
    if (errno != EAGAIN && errno != EWOULDBLOCK && errno != EINTR) return -1;
    pollfd pfd{.fd = fd_, .events = POLLIN, .revents = 0};
    ::poll(&pfd, 1, -1);
  }
}

bool UdpSocket::send_to(std::span<const std::byte> data, const sockaddr_in& to) noexcept {
  const ssize_t n =
      ::sendto(fd_, data.data(), data.size(), 0, reinterpret_cast<const sockaddr*>(&to), sizeof to);
  return n == static_cast<ssize_t>(data.size());
}

int UdpSocket::rcvbuf() const {
  int value = 0;
  socklen_t len = sizeof value;
  if (::getsockopt(fd_, SOL_SOCKET, SO_RCVBUF, &value, &len) != 0) throw_errno("getsockopt SO_RCVBUF");
  return value;
}

std::uint16_t UdpSocket::local_port() const {
  sockaddr_in sa{};
  socklen_t len = sizeof sa;
  if (::getsockname(fd_, reinterpret_cast<sockaddr*>(&sa), &len) != 0) throw_errno("getsockname");
  return ntohs(sa.sin_port);
}

UdpCounters read_udp_counters() {
  // /proc/net/snmp has two "Udp:" lines: field names, then values.
  std::ifstream in("/proc/net/snmp");
  std::string line;
  std::vector<std::string> names;
  UdpCounters c;
  while (std::getline(in, line)) {
    if (line.rfind("Udp:", 0) != 0) continue;
    std::istringstream fields(line.substr(4));
    std::vector<std::string> tokens;
    for (std::string t; fields >> t;) tokens.push_back(t);
    if (names.empty()) {
      names = tokens;
      continue;
    }
    for (std::size_t i = 0; i < names.size() && i < tokens.size(); ++i) {
      if (names[i] == "InDatagrams") c.in_datagrams = std::stoull(tokens[i]);
      if (names[i] == "RcvbufErrors") c.rcvbuf_errors = std::stoull(tokens[i]);
    }
    break;
  }
  return c;
}

}  // namespace hft::net
