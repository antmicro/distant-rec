#!/bin/bash

find . -name "*.o" -type f -delete
find . -name "*.h" -type f -delete
find . -name "*.cpp" -type f -delete
find . -name "*.c" -type f -delete
find . -name "*.md" -type f -delete
find . -name "*.hpp" -type f -delete
find . -name "*.c++" -type f -delete
find . -name "*.png" -type f -delete
find . -name "*.svg" -type f -delete
find . -name "*.cmake" -type f -delete
find . -name "*.make" -type f -delete
find . -name "*.rst" -type f -delete
find . -name "*.html" -type f -delete
rm -rf .git
make
./vtr_flow/scripts/run_vtr_task.pl -d -l vtr_flow/tasks/regression_tests/$1/task_list.txt

if [ $1 = "vtr_reg_nightly" ] || [ $1 = "vtr_reg_nightly" ]; then
	cd build
	make
	cd ..
fi

find . -type l -exec rm -f {} \;
