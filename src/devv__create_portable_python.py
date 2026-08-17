import os
import shutil

os.environ["DEV"] = "1"
os.environ["PIP_INSTALL_NAMES"] = "pip requests"
os.environ["PIP_INSTALL_NAMES_2"] = "requests"
os.environ["PIP_INSTALL_REQUIREMENTS_4"] = "some_requirements.txt"
os.environ["PIP_INSTALL_NAMES_6"] = "omegaconf"
os.environ["PIP_INSTALL_REQUIREMENTS_7"] = "https://github.com/TimPeTwo/obs-screen-recognition/raw/master/requirements.txt"

from create_portable_python import make_parser, main

if __name__ == '__main__':

	def setup():
		parser = make_parser()
		args = []
		args = parser.parse_args(args)
		args.python_version = "3.8"

		shutil.rmtree("../dev/dev_out/python/python38.zip", ignore_errors = True)

		args.output_dir = "../dev/dev_out/"
		main(args)


	setup()
