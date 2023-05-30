# GBX Compiler (gbxc)
Compile XML files to GBX.  
This tool was created in order to replace the manual labor of hex editing the GBX files directly.  
Usage:  
`gbxc [-h] [-d DIR] [-l LOGFILE] [-c] [-v] file.xml`  
  
positional arguments:  
file.xml - xml input file that will be "compiled" to gbx  
  
options:  
-h, --help - show this help message and exit  
-d DIR, --dir DIR           - the directory where the output file will be saved  
-l LOGFILE, --log LOGFILE   - log file path  
-c, --checksum              - whether the program should do a md5 checksum on the compiled file  
-v, --verbose               - show additional information when compiling  
  
## Documentation
Check the documentation [here](https://github.com/GreffMASTER/gbxc/tree/main/Doc) as well as the sample files [here](https://github.com/GreffMASTER/gbxc/tree/main/Samples/TM1.0/GameData).

## License
GBX Compiler is licensed under the MIT License, see [LICENSE](https://github.com/GreffMASTER/gbxc/blob/main/LICENSE) for details.
