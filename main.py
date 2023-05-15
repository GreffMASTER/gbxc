import os
import sys
import hashlib
import xml.etree.ElementTree as ET
import gbx_xml as gbx_xml_tools
from gbx import xml_to_gbx
import argparse

VERSION_STR = 'a1.1'


def is_valid_file(parser, arg):
    if not os.path.exists(arg):
        parser.error(f'The file {arg} does not exist!')
    else:
        return arg  # return the file path


arg_parser = argparse.ArgumentParser(
        prog='gbxc',
        description=f'GBXCompiler v.{VERSION_STR} - "Compile" xml files to gbx.',
        epilog='This program is still in it\'s early stage of development. '
        'Expect bugs and error. Some things might change in future versions.'
        )


arg_parser.add_argument(dest='xml_file',
                        help='xml input file that will be "compiled" to gbx',
                        metavar='file.xml',
                        type=lambda x: is_valid_file(arg_parser, x))
arg_parser.add_argument('-d', '--dir', dest='dir',
                        help='the directory where the output file will be saved'
                        )


def main() -> int:
    argv = arg_parser.parse_args()
    xml_path = argv.xml_file
    gbx_path = f'{xml_path[:-4]}.Gbx'
    if argv.dir:
        gbx_path = os.path.join(argv.dir, gbx_path)

    print(f'-------GBXC v.{VERSION_STR}-------')
    print(f'Parsing "{xml_path}"...')
    gbx = ET.parse(xml_path)
    if gbx_xml_tools.validate_gbx_xml(gbx, xml_path) == 1:
        sys.exit('XML parsing failed!')

    # Writing
    if xml_to_gbx(xml_path, gbx_path, gbx.getroot()) != 0:
        sys.exit(f'There was an error while writing the "{gbx_path}" GBX file!')

    print(f'Successfully compiled to "{gbx_path}"!')

    with open(gbx_path, 'rb') as fb:
        gbx_data = fb.read()
        new_md5 = hashlib.md5(gbx_data).digest().hex()
        fb.close()
        print(f'{new_md5}')
        exp_md5 = gbx.getroot().get('md5')
        if exp_md5:
            if new_md5 == exp_md5:
                print('CHECKSUM: OK')
            else:
                print(f'CHECKSUM: FAIL, expected checksum is incorrect!\n'
                      f'Expected "{exp_md5}", got "{new_md5}".')
    return 0


if __name__ == '__main__':
    main()
