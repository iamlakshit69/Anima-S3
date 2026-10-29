cmake_minimum_required(VERSION 3.16)

# ANIMA-S3 firmware — top-level CMakeLists.txt
# Phase 0 stub. Full ESP-IDF build configuration comes in Phase 2.
#
# To build (requires ESP-IDF 5.x environment):
#   idf.py set-target esp32s3
#   idf.py build
# HUMAN APPROVAL REQUIRED before `idf.py flash` (Notes for agents.md section 7).

include($ENV{IDF_PATH}/tools/cmake/project.cmake)

project(anima_s3)
