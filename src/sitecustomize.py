def setup():
	import sys, os
	root_dir = os.path.abspath(os.path.dirname(os.path.abspath(__file__)))
	sys.path.append(root_dir)
	sys.path.append(os.path.join(root_dir, r"Lib", "site-packages"))


setup()
