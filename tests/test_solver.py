import unittest
from fractions import Fraction

from app import solve_linear_program


class SolverMethodsTest(unittest.TestCase):
    def setUp(self):
        self.costs = [Fraction(3), Fraction(2)]
        self.constraints = [
            ([Fraction(1), Fraction(1)], "<=", Fraction(4)),
            ([Fraction(1), Fraction(0)], "<=", Fraction(2)),
            ([Fraction(0), Fraction(1)], "<=", Fraction(3)),
        ]

    def test_known_maximum_with_each_method(self):
        for method in ("Simplex", "Gran M", "Dos Fases"):
            with self.subTest(method=method):
                result = solve_linear_program(
                    2, self.costs, self.constraints, method, "Maximizar",
                )
                self.assertEqual(result["status"], "optimal")
                self.assertEqual(result["objective"], Fraction(10))
                self.assertEqual(result["values"], [Fraction(2), Fraction(2)])


if __name__ == "__main__":
    unittest.main()