#!/usr/bin/env python

import numpy as np
import pytest

from shakelib.correlation.loth_baker_2013 import LothBaker2013


def test_loth_baker_2012():
    #
    # Pick some common periods
    #
    t1 = np.array([0.01, 0.3, 1.0, 2.0, 3.0])
    lb13 = LothBaker2013(t1)
    #
    # Distances from 0 to 400
    #
    d = np.linspace(0.0, 400.0, 201).reshape((1, -1))
    #
    # Random cross correlations to the periods in t1
    #
    ix1 = np.array(
        [
            0,
            2,
            1,
            0,
            1,
            1,
            2,
            0,
            3,
            4,
            1,
            0,
            2,
            1,
            2,
            2,
            2,
            2,
            0,
            0,
            2,
            1,
            1,
            3,
            0,
            1,
            1,
            0,
            3,
            1,
            3,
            4,
            3,
            4,
            1,
            0,
            1,
            1,
            3,
            3,
            4,
            1,
            0,
            4,
            0,
            1,
            1,
            3,
            3,
            2,
            0,
            1,
            1,
            0,
            2,
            3,
            2,
            0,
            1,
            4,
            2,
            4,
            4,
            4,
            3,
            2,
            1,
            1,
            3,
            2,
            4,
            4,
            3,
            1,
            3,
            1,
            3,
            1,
            4,
            1,
            4,
            2,
            3,
            2,
            0,
            4,
            2,
            1,
            0,
            1,
            2,
            1,
            2,
            2,
            0,
            2,
            0,
            4,
            4,
            3,
            0,
            4,
            4,
            0,
            4,
            0,
            0,
            3,
            1,
            3,
            1,
            3,
            1,
            0,
            3,
            3,
            1,
            1,
            4,
            0,
            1,
            2,
            4,
            1,
            3,
            4,
            1,
            0,
            3,
            4,
            1,
            4,
            2,
            4,
            4,
            4,
            2,
            4,
            2,
            2,
            0,
            3,
            2,
            3,
            2,
            4,
            3,
            4,
            4,
            0,
            1,
            1,
            1,
            0,
            3,
            2,
            0,
            0,
            3,
            4,
            3,
            0,
            3,
            4,
            2,
            3,
            2,
            4,
            2,
            4,
            1,
            3,
            0,
            0,
            3,
            4,
            2,
            0,
            3,
            2,
            2,
            0,
            2,
            2,
            0,
            2,
            4,
            2,
            0,
            0,
            0,
            1,
            1,
            2,
            3,
            2,
            0,
            3,
            0,
            1,
            4,
        ]
    ).reshape((1, -1))
    ix2 = np.array(
        [
            2,
            4,
            0,
            2,
            3,
            1,
            3,
            1,
            3,
            2,
            1,
            0,
            3,
            2,
            4,
            3,
            2,
            3,
            1,
            4,
            3,
            4,
            1,
            0,
            2,
            1,
            1,
            3,
            0,
            1,
            2,
            0,
            3,
            2,
            1,
            1,
            2,
            1,
            2,
            1,
            4,
            4,
            1,
            0,
            3,
            3,
            0,
            4,
            4,
            0,
            1,
            1,
            0,
            2,
            3,
            0,
            1,
            4,
            1,
            3,
            4,
            3,
            4,
            2,
            3,
            4,
            3,
            4,
            0,
            0,
            2,
            2,
            1,
            3,
            3,
            3,
            0,
            0,
            2,
            0,
            4,
            3,
            2,
            4,
            4,
            1,
            3,
            2,
            3,
            2,
            1,
            2,
            2,
            3,
            3,
            1,
            4,
            2,
            0,
            2,
            4,
            0,
            1,
            3,
            3,
            3,
            1,
            3,
            2,
            3,
            2,
            1,
            0,
            3,
            3,
            0,
            1,
            2,
            0,
            1,
            3,
            3,
            2,
            4,
            0,
            2,
            0,
            1,
            2,
            4,
            4,
            2,
            3,
            4,
            2,
            2,
            4,
            2,
            3,
            0,
            3,
            3,
            2,
            4,
            3,
            2,
            2,
            4,
            1,
            2,
            1,
            2,
            2,
            1,
            3,
            1,
            2,
            1,
            3,
            2,
            1,
            3,
            0,
            0,
            3,
            0,
            0,
            2,
            3,
            2,
            2,
            1,
            2,
            4,
            0,
            2,
            2,
            3,
            2,
            1,
            0,
            3,
            0,
            3,
            1,
            0,
            2,
            1,
            4,
            2,
            4,
            2,
            3,
            4,
            4,
            3,
            2,
            0,
            1,
            4,
            1,
        ]
    ).reshape((1, -1))
    lb13.getCorrelation(ix1, ix2, d)

    cor_target = np.array(
        [
            [
                4.30000000e-01,
                4.88469538e-01,
                4.66019054e-01,
                2.81962129e-01,
                1.59661735e-01,
                3.49853397e-01,
                2.84822022e-01,
                2.49519005e-01,
                3.06988586e-01,
                1.80783930e-01,
                2.00830388e-01,
                1.93767392e-01,
                1.53139801e-01,
                1.00184912e-01,
                1.11628973e-01,
                1.16011908e-01,
                1.24513037e-01,
                9.69525290e-02,
                8.72591618e-02,
                2.84133702e-02,
                7.44327485e-02,
                2.87497435e-02,
                6.71425231e-02,
                2.09894447e-02,
                3.46454195e-02,
                5.17771403e-02,
                4.74962384e-02,
                1.48558674e-02,
                1.36301797e-02,
                3.66842646e-02,
                3.13643960e-02,
                1.00625216e-02,
                3.54347184e-02,
                2.12857024e-02,
                2.38773469e-02,
                2.00871176e-02,
                1.35597457e-02,
                1.84594815e-02,
                1.57869637e-02,
                6.94993750e-03,
                1.74079488e-02,
                5.16021298e-03,
                1.10213436e-02,
                3.59490965e-03,
                3.45305835e-03,
                4.15531977e-03,
                7.82196711e-03,
                8.72210334e-03,
                8.00559785e-03,
                4.04888007e-03,
                5.55146434e-03,
                5.55866353e-03,
                4.67686844e-03,
                2.87362014e-03,
                4.00519093e-03,
                1.34494706e-03,
                2.44149870e-03,
                1.08270402e-03,
                3.05063185e-03,
                3.11822695e-03,
                2.10275509e-03,
                2.62698100e-03,
                2.64082810e-03,
                1.62597046e-03,
                2.28006661e-03,
                1.36981540e-03,
                6.86854799e-04,
                5.55636797e-04,
                4.41341723e-04,
                7.29158972e-04,
                8.92350945e-04,
                8.19050032e-04,
                4.10689323e-04,
                3.76953834e-04,
                9.67597788e-04,
                3.17568688e-04,
                2.22317139e-04,
                5.48681797e-04,
                4.49504137e-04,
                4.62242702e-04,
                5.64527791e-04,
                3.95857902e-04,
                3.63340723e-04,
                2.92824545e-04,
                1.07010634e-04,
                1.18778156e-04,
                2.57877296e-04,
                1.71266633e-04,
                7.94822268e-05,
                1.44285363e-04,
                1.32433249e-04,
                1.21554711e-04,
                1.80517387e-04,
                1.41526060e-04,
                4.75246117e-05,
                8.62721911e-05,
                3.82581562e-05,
                8.81970571e-05,
                3.22309831e-05,
                8.46223278e-05,
                2.71533283e-05,
                2.49228572e-05,
                2.76635223e-05,
                2.19731037e-05,
                6.58826386e-05,
                1.85114706e-05,
                4.56865682e-05,
                5.71823329e-05,
                2.83101839e-05,
                4.81738535e-05,
                2.38502101e-05,
                1.45120569e-05,
                2.73172571e-05,
                9.32478853e-06,
                3.13823297e-05,
                7.85576546e-06,
                2.11506971e-05,
                1.30892728e-05,
                5.80455228e-06,
                1.49920285e-05,
                6.70967988e-06,
                1.28389545e-05,
                1.03472052e-05,
                4.57274947e-06,
                3.63212961e-06,
                8.00105651e-06,
                8.22779971e-06,
                7.55193894e-06,
                7.04616761e-06,
                8.46541967e-06,
                2.50957812e-06,
                4.78405198e-06,
                5.00094415e-06,
                6.00824353e-06,
                3.69930522e-06,
                3.39543112e-06,
                3.11651831e-06,
                2.86051640e-06,
                2.99020220e-06,
                1.80740393e-06,
                9.21631853e-07,
                3.10172768e-06,
                2.48460281e-06,
                2.32801928e-06,
                1.78792422e-06,
                1.44092877e-06,
                1.50625543e-06,
                1.80964818e-06,
                5.36471155e-07,
                7.67013150e-07,
                1.14727223e-06,
                7.09998310e-07,
                6.51676520e-07,
                8.13209036e-07,
                1.01783066e-06,
                5.03913913e-07,
                4.20945742e-07,
                5.77166653e-07,
                7.22394720e-07,
                4.33999404e-07,
                2.17616664e-07,
                1.52344721e-07,
                1.39830583e-07,
                1.22640205e-07,
                3.21991408e-07,
                1.08125080e-07,
                1.78637942e-07,
                2.18618647e-07,
                2.28530051e-07,
                1.84177562e-07,
                1.39308537e-07,
                8.47645954e-08,
                1.06812544e-07,
                5.20451728e-08,
                4.99918573e-08,
                1.10124835e-07,
                1.34771719e-07,
                3.86565906e-08,
                9.69819482e-08,
                6.44095935e-08,
                5.38047142e-08,
                2.74361130e-08,
                4.53283433e-08,
                6.31778290e-08,
                5.70452799e-08,
                3.50504923e-08,
                4.28950934e-08,
                3.24450634e-08,
                1.43880466e-08,
                2.48767223e-08,
                1.21213601e-08,
                2.30275462e-08,
                1.40114934e-08,
                2.35413264e-08,
                2.94102873e-08,
                2.25871690e-08,
                1.36526346e-08,
                6.96175478e-09,
                1.71817081e-08,
                6.77733681e-09,
                6.22062223e-09,
            ]
        ]
    ).reshape((1, -1))

    np.testing.assert_allclose(d, cor_target)

    #
    # Test error checks
    #
    ix3 = ix2[1:-1]
    with pytest.raises(ValueError) as e:
        lb13.getCorrelation(ix1, ix3, d)

    d = np.linspace(-1.0, 400.0, 201)
    with pytest.raises(ValueError) as e:
        lb13.getCorrelation(ix1, ix2, d)

    t1 = np.array([0.001, 0.3, 1.0, 2.0, 3.0])
    with pytest.raises(ValueError) as e:
        lb13 = LothBaker2013(t1)

    t1 = np.array([0.01, 0.3, 1.0, 2.0, 3.0, 20.0])
    with pytest.raises(ValueError) as e:  # noqa
        lb13 = LothBaker2013(t1)


if __name__ == "__main__":
    test_loth_baker_2012()
