foreach(app itch_stats itch_synth pipeline)
  add_executable(${app} ${app}.cpp)
  target_link_libraries(${app} PRIVATE hft::core hft::warnings)
endforeach()
