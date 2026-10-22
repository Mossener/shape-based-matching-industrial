import importlib.util
from pathlib import Path
import sys
import unittest
here=Path(sys.argv[1]);sys.path.insert(0,str(here))
import test_independent_geometry as tests
spec=importlib.util.spec_from_file_location('independent_numeric_mutant',sys.argv[2])
mutant=importlib.util.module_from_spec(spec);spec.loader.exec_module(mutant)
mutant.HERE=here;mutant.EXPERIMENT=here.parent
tests.independent=mutant
suite=unittest.TestSuite([tests.IndependentGeometryTests(sys.argv[3])])
result=unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
