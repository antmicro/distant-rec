#!/bin/bash

cd vtr-verilog-to-routing
make
./vtr_flow/scripts/run_vtr_task.pl -d -l vtr_flow/tasks/regression_tests/$1/task_list.txt

if [ $1 = "vtr_reg_nightly" ] || [ $1 = "vtr_reg_nightly" ]; then
	cd build
	make
	cd ..
	./dev/upgrade_vtr_archs.sh
fi

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

find . -type l -exec rm -f {} \;

mv build/abc/abc abc/abc && \
mv build/vpr/vpr vpr/vpr && \
mv build/ace2/ace ace2/ace && \
mv  build/ODIN_II/odin_II ODIN_II/odin_II
