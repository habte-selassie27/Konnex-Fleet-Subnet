# simulation/CMakeLists.txt — ament_cmake package (Phase 1).
#
# Installs the warehouse world, robot model, sensor configs, scenario
# generator, bridge config, launch files, and the fleet_agent program so the
# whole simulation tree is available via FindPackageShare("simulation") after
# `colcon build`.

cmake_minimum_required(VERSION 3.8)
project(simulation)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)

# ─── Install data (worlds, models, sensors, scenarios, bridge, maps) ────────
install(
  DIRECTORY worlds robots sensors scenarios bridge
  DESTINATION share/${PROJECT_NAME}
)

# ─── Install launch files ───────────────────────────────────────────────────
install(
  DIRECTORY launch
  DESTINATION share/${PROJECT_NAME}
)

# ─── Install the fleet_agent program (runnable via `ros2 run simulation`) ───
install(
  PROGRAMS robots/fleet_agent.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()
