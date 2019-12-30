#!/bin/bash

RBE="/b/f/w"
P1="${PWD//\//\\/}"
P2="${RBE//\//\\/}"

echo "Your current directory is ${PWD}. We'll change all occurences of it to ${RBE}."

read -p "Are you sure? " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
	echo "Starting substitution..."
	grep -rl "$PWD" build/env/conda --binary-file=without-match | xargs sed -i "s/$P1/$P2/g"
fi
