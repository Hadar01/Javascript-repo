#pragma once

// UdpSocket: a thin RAII wrapper around a Linux UDP socket.
//
// Setup (open, bind, join a multicast group, set buffer sizes) throws
// std::system_error. It runs once at startup. The hot-path calls (try_recv,
// send_to) are noexcept and report errors as return values.

#include <netinet/in.h>

#include <cstddef>
#include <cstdint>
#include <span>
#include <string>
#include <string_view>

namespace hft::net {

// An IPv4 address and port, such as "239.255.1.1:30001".
struct Endpoint {
  std::string ip;
  std::uint16_t port = 0;

  // Throws std::invalid_argument for anything that isn't "a.b.c.d:port".
  static Endpoint parse(std::string_view text);
  [[nodiscard]] sockaddr_in to_sockaddr() const;
  [[nodiscard]] bool is_multicast() const;  // 224.0.0.0 - 239.255.255.255
};

class UdpSocket {
 public:
  // A socket for sending. ttl 1 keeps multicast on the local network.
  // loopback: deliver our own multicast packets to receivers on this host
  // (needed when sender and receiver share a machine, as in testing).
  static UdpSocket open_sender(int ttl = 1, bool multicast_loopback = true);

  // A non-blocking socket receiving on `ep`. For a multicast address it
  // binds the group's port and joins the group; for a unicast address it
  // binds that address. rcvbuf_bytes asks for a receive buffer of that
  // size; the kernel caps it at net.core.rmem_max (see rcvbuf()).
  static UdpSocket open_receiver(const Endpoint& ep, int rcvbuf_bytes = 4 << 20);

  UdpSocket(const UdpSocket&) = delete;
  UdpSocket& operator=(const UdpSocket&) = delete;
  UdpSocket(UdpSocket&& other) noexcept;
  UdpSocket& operator=(UdpSocket&& other) noexcept;
  ~UdpSocket();

  // Non-blocking receive: the datagram's size, 0 if nothing is waiting, or
  // -1 on a real error. A datagram larger than buf is truncated (and the
  // returned size is still its full size, so the caller can detect it).
  [[nodiscard]] std::ptrdiff_t try_recv(std::span<std::byte> buf) noexcept;

  // Blocking receive, for comparison in the benchmarks: waits until a datagram
  // arrives.
  [[nodiscard]] std::ptrdiff_t recv_blocking(std::span<std::byte> buf) noexcept;

  bool send_to(std::span<const std::byte> data, const sockaddr_in& to) noexcept;

  // The receive buffer the kernel actually granted. Linux reports double
  // the usable size, because it counts its own bookkeeping overhead.
  [[nodiscard]] int rcvbuf() const;
  // The port this socket is bound to. Bind to port 0 and the kernel picks a
  // free one: tests do that to avoid clashes.
  [[nodiscard]] std::uint16_t local_port() const;
  [[nodiscard]] int fd() const noexcept { return fd_; }

 private:
  explicit UdpSocket(int fd) noexcept : fd_(fd) {}
  int fd_ = -1;
};

// Linux UDP counters from /proc/net/snmp, to tell our own losses (the
// socket's receive buffer overflowed: RcvbufErrors) from losses elsewhere.
struct UdpCounters {
  std::uint64_t in_datagrams = 0;
  std::uint64_t rcvbuf_errors = 0;
};
UdpCounters read_udp_counters();

}  // namespace hft::net
