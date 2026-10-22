import importlib.util, pathlib, sys, unittest
sys.dont_write_bytecode=True
here=pathlib.Path(sys.argv[1]); name=sys.argv[2]; mutant=pathlib.Path(sys.argv[3])
sys.path.insert(0,str(here))
origin=here/(name+'.py')
spec=importlib.util.spec_from_file_location(name,origin)
module=importlib.util.module_from_spec(spec);sys.modules[name]=module
exec(compile(mutant.read_text(encoding='utf-8'),str(origin),'exec'),module.__dict__)
suite=unittest.defaultTestLoader.discover(str(here),pattern='test_*.py')
result=unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
