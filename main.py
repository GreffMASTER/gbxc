import os
import sys
import hashlib
import xml.etree.ElementTree
import xml.etree.ElementTree as ET
import gbx_xml as gbx_xml_tools
from gbx import xml_to_gbx
from gbxerrors import ValidationError, GBXWriteError
import argparse
import logging


VERSION_STR = 'a1.6.3'


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
arg_parser.add_argument('-o', '--out', dest='out',
                        help='output path'
                        )
arg_parser.add_argument('-d', '--dir', dest='dir',
                        help='the directory where the output file will be saved (only without -o)'
                        )
arg_parser.add_argument('-l', '--log', dest='logfile',
                        help='log file path'
                        )
arg_parser.add_argument('-c', '--checksum', dest='do_checksum', action='store_true',
                        help='whether the program should do a md5 checksum on the compiled file'
                        )
arg_parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
                        help='show additional information when compiling'
                        )


def main() -> None:
    argv = arg_parser.parse_args()
    xml_path = argv.xml_file
    gbx_path = f'{xml_path[:-4]}.Gbx'
    if argv.out:
        gbx_path = argv.out
    else:
        if argv.dir:
            gbx_path = os.path.join(argv.dir, gbx_path)

    loglevel = logging.WARNING
    logfile = None
    if argv.verbose:
        loglevel = logging.INFO
    if argv.logfile:
        logfile = argv.logfile

    logging.basicConfig(
        level=loglevel,
        format='%(asctime)s (%(levelname)s) %(message)s',
        filename=logfile
    )

    print(f'-------GBXC v.{VERSION_STR}-------')
    logging.info(f'Logging level set to {loglevel}')
    print(f'Parsing "{xml_path}"...')
    gbx_tree: ET.ElementTree
    og_cwd = os.getcwd()
    try:
        gbx_tree = ET.parse(xml_path)
    except xml.etree.ElementTree.ParseError as e:
        logging.error(f'Failed to parse XML file! ({e.code}, {e.position})')
        sys.exit(f'Failed to parse XML file! (code: {e.code}, pos: {e.position})')
    os.chdir(og_cwd)
    try:
        gbx_xml_tools.validate_gbx_xml(gbx_tree, xml_path)
    except ValidationError:
        logging.error('GBX XML parsing failed!')
        sys.exit('GBX XML parsing failed!')

    # Writing
    try:
        xml_to_gbx(xml_path, gbx_path, gbx_tree.getroot())
    except GBXWriteError:
        sys.exit(f'There was an error while writing the "{gbx_path}" GBX file!')

    print(f'Successfully compiled to "{gbx_path}"!')
    logging.info(f'Successfully compiled to "{gbx_path}"!')

    if argv.do_checksum:
        with open(gbx_path, 'rb') as fb:
            gbx_data = fb.read()
            new_md5 = hashlib.md5(gbx_data).digest().hex()
            fb.close()
            print(f'{new_md5}')
            exp_md5 = gbx_tree.getroot().get('md5')
            if exp_md5:
                if new_md5 == exp_md5:
                    print('MD5 Checksum: OK')
                    logging.info('MD5 Checksum: OK')
                else:
                    print(f'MD5 Checksum: FAIL, expected checksum is incorrect!\n'
                          f'Expected "{exp_md5}", got "{new_md5}".')
                    logging.warning(f'MD5 Checksum: FAIL, expected checksum is incorrect!\n'
                                    f'Expected "{exp_md5}", got "{new_md5}".')


if __name__ == '__main__':
    main()
