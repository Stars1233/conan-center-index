cmake_minimum_required(VERSION 3.15)
project(test_package LANGUAGES CXX)

find_package(log4cxx REQUIRED CONFIG)

add_executable(${PROJECT_NAME} test_package.cpp)
target_compile_features(${PROJECT_NAME} PUBLIC cxx_std_17)
target_link_libraries(${PROJECT_NAME} PRIVATE log4cxx )
