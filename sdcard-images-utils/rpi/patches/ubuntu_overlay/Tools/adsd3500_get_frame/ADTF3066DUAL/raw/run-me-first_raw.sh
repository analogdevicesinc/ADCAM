
#!/bin/bash

mipi_file="set-mipi.txt"

main() {
echo Resetting the ADSD3500
../../../adsd3500_scripts/adi-adsd3500-reset.sh
echo Waiting 3s for reset to complete
sleep 3
echo Setting MIPI to 2.5Gbps

set_mipi="R 01 12
W 00 31 00 01
W 00 AB 00 01
W 00 33 00 01
R 01 12"

echo "$set_mipi" > $mipi_file 

output=$(../../../ctrl_app/ctrl_app $mipi_file | sed 's/[[:space:]]*$//')
expected_output="Burst Control app version: 1.2.0
59 31
59 31"

if [[ "$output" == "$expected_output" ]]; then
  echo "Success."
else
  echo "Error."
  echo "Actual Output:"
  echo "$output" | cat -A
fi
}

clean_up() {
if [ -f $mipi_file ]; then
  rm $mipi_file
fi
}

trap clean_up EXIT
main
