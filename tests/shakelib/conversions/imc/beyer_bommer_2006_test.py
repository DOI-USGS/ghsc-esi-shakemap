#!/usr/bin/env python

# stdlib imports
import os.path
import sys

# third party imports
import numpy as np
from openquake.hazardlib import const
from openquake.hazardlib.imt import IMT, PGA, PGV, SA
import pytest

# local imports
from shakelib.conversions.imc.beyer_bommer_2006 import BeyerBommer2006


# important constants
homedir = os.path.dirname(os.path.abspath(__file__))  # where is this script?
shakedir = os.path.abspath(os.path.join(homedir, "..", "..", "..", ".."))
sys.path.insert(0, shakedir)

amps_in = np.log(np.array([0.05, 0.1, 0.2, 0.4, 0.8, 1.6]))
sigmas_in = np.array([0.5, 0.55, 0.6, 0.65, 0.61, 0.7])
imc_in = [
    const.IMC.MEDIAN_HORIZONTAL,
    const.IMC.MEDIAN_HORIZONTAL,
    const.IMC.GMRotI50,
    const.IMC.GREATER_OF_TWO_HORIZONTAL,
    const.IMC.GREATER_OF_TWO_HORIZONTAL,
    const.IMC.HORIZONTAL,
]
imc_out = [
    const.IMC.GREATER_OF_TWO_HORIZONTAL,
    const.IMC.GMRotI50,
    const.IMC.GREATER_OF_TWO_HORIZONTAL,
    const.IMC.GMRotI50,
    const.IMC.MEDIAN_HORIZONTAL,
    const.IMC.MEDIAN_HORIZONTAL,
]
imt_in = [PGA(), PGV(), SA(0.3), SA(1.0), SA(3.0)]

amps_target = np.array(
    [
        [-2.90042209, -2.20727491, -1.51412773, -0.82098055, -0.12783337, 0.56531381],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.90042209, -2.20727491, -1.51412773, -0.82098055, -0.12783337, 0.56531381],
        [-3.09104245, -2.39789527, -1.70474809, -1.01160091, -0.31845373, 0.37469345],
        [-3.09104245, -2.39789527, -1.70474809, -1.01160091, -0.31845373, 0.37469345],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.90042209, -2.20727491, -1.51412773, -0.82098055, -0.12783337, 0.56531381],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.90042209, -2.20727491, -1.51412773, -0.82098055, -0.12783337, 0.56531381],
        [-3.09104245, -2.39789527, -1.70474809, -1.01160091, -0.31845373, 0.37469345],
        [-3.09104245, -2.39789527, -1.70474809, -1.01160091, -0.31845373, 0.37469345],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.86347036, -2.17032318, -1.477176, -0.78402882, -0.09088164, 0.60226554],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.86347036, -2.17032318, -1.477176, -0.78402882, -0.09088164, 0.60226554],
        [-3.12799418, -2.434847, -1.74169982, -1.04855264, -0.35540546, 0.33774172],
        [-3.12799418, -2.434847, -1.74169982, -1.04855264, -0.35540546, 0.33774172],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.81341072, -2.12026354, -1.42711636, -0.73396918, -0.04082199, 0.65232519],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.81341072, -2.12026354, -1.42711636, -0.73396918, -0.04082199, 0.65232519],
        [-3.17805383, -2.48490665, -1.79175947, -1.09861229, -0.40546511, 0.28768207],
        [-3.17805383, -2.48490665, -1.79175947, -1.09861229, -0.40546511, 0.28768207],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.81341072, -2.12026354, -1.42711636, -0.73396918, -0.04082199, 0.65232519],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
        [-2.81341072, -2.12026354, -1.42711636, -0.73396918, -0.04082199, 0.65232519],
        [-3.17805383, -2.48490665, -1.79175947, -1.09861229, -0.40546511, 0.28768207],
        [-3.17805383, -2.48490665, -1.79175947, -1.09861229, -0.40546511, 0.28768207],
        [-2.99573227, -2.30258509, -1.60943791, -0.91629073, -0.22314355, 0.47000363],
    ]
)

sigs_target = np.array(
    [
        [0.5123436, 0.56313139, 0.61395436, 0.66480445, 0.62412242, 0.71567588],
        [0.50029991, 0.55027266, 0.60024995, 0.65023073, 0.61024585, 0.70021425],
        [0.5120389, 0.56285419, 0.61370012, 0.66456967, 0.62387233, 0.71545778],
        [0.48814882, 0.53735522, 0.58653034, 0.63568144, 0.59636229, 0.68481368],
        [0.48784144, 0.537076, 0.58627454, 0.63544542, 0.59611071, 0.68459461],
        [0.48076008, 0.52973252, 0.57863271, 0.62747753, 0.58840566, 0.67627899],
        [0.5123436, 0.56313139, 0.61395436, 0.66480445, 0.62412242, 0.71567588],
        [0.50029991, 0.55027266, 0.60024995, 0.65023073, 0.61024585, 0.70021425],
        [0.5120389, 0.56285419, 0.61370012, 0.66456967, 0.62387233, 0.71545778],
        [0.48814882, 0.53735522, 0.58653034, 0.63568144, 0.59636229, 0.68481368],
        [0.48784144, 0.537076, 0.58627454, 0.63544542, 0.59611071, 0.68459461],
        [0.48076008, 0.52973252, 0.57863271, 0.62747753, 0.58840566, 0.67627899],
        [0.51248419, 0.56325931, 0.61407169, 0.66491281, 0.62423784, 0.71577653],
        [0.5009647, 0.55087715, 0.60080415, 0.65074237, 0.61079099, 0.7006894],
        [0.51150308, 0.56236679, 0.61325313, 0.66415691, 0.62343263, 0.71507441],
        [0.48868846, 0.53784549, 0.58697954, 0.63609593, 0.59680409, 0.68519845],
        [0.48769948, 0.53694706, 0.58615642, 0.63533644, 0.59599454, 0.68449346],
        [0.469213, 0.51747452, 0.56562716, 0.61369652, 0.57524702, 0.66170077],
        [0.51437714, 0.56498216, 0.61565237, 0.6663729, 0.62579284, 0.71713307],
        [0.50119856, 0.55108983, 0.60099917, 0.65092242, 0.61098281, 0.70085662],
        [0.51316212, 0.56387619, 0.61463758, 0.66543547, 0.62479453, 0.71626207],
        [0.48701383, 0.53632437, 0.58558606, 0.63481027, 0.5954336, 0.6840051],
        [0.48578027, 0.53520447, 0.58456055, 0.6338644, 0.59442508, 0.68312735],
        [0.4649541, 0.51361597, 0.56209924, 0.61044647, 0.57177846, 0.65868763],
        [0.51437714, 0.56498216, 0.61565237, 0.6663729, 0.62579284, 0.71713307],
        [0.50119856, 0.55108983, 0.60099917, 0.65092242, 0.61098281, 0.70085662],
        [0.51316212, 0.56387619, 0.61463758, 0.66543547, 0.62479453, 0.71626207],
        [0.48701383, 0.53632437, 0.58558606, 0.63481027, 0.5954336, 0.6840051],
        [0.48578027, 0.53520447, 0.58456055, 0.6338644, 0.59442508, 0.68312735],
        [0.4649541, 0.51361597, 0.56209924, 0.61044647, 0.57177846, 0.65868763],
    ]
)


def test_bb06():
    amps_out = np.empty([0, 6])
    sigs_out = np.empty([0, 6])
    for imt in imt_in:
        for i in range(len(imc_in)):
            bb06 = BeyerBommer2006(imc_in[i], imc_out[i])
            tmp = bb06.convertAmps(imt, amps_in)
            amps_out = np.vstack((amps_out, tmp))
            tmp = bb06.convertSigmas(imt, sigmas_in)
            sigs_out = np.vstack((sigs_out, tmp))
    np.testing.assert_allclose(amps_out, amps_target, atol=1e-5)
    np.testing.assert_allclose(sigs_out, sigs_target, atol=1e-5)

    # Test that an invalid/unknown parameter is changed to AVERAGE_HORIZONTAL
    bb06 = BeyerBommer2006("wrong", imc_out[0])
    assert bb06.imc_in.value == "Average horizontal"
    assert bb06.imc_out == imc_out[0]
    bb06 = BeyerBommer2006(imc_out[0], "wrong")
    assert bb06.imc_in == imc_out[0]
    assert bb06.imc_out.value == "Average horizontal"
    bb06 = BeyerBommer2006("wrong", "wrong")
    assert bb06.imc_in.value == "Average horizontal"
    assert bb06.imc_out.value == "Average horizontal"

    # Test that the correct input/output imc returns the right path
    bb06 = BeyerBommer2006("Median horizontal", "Random horizontal")
    assert len(bb06.path) == 2
    assert bb06.path[0].value == "Median horizontal"
    assert bb06.path[-1].value == "Random horizontal"
    bb06 = BeyerBommer2006("Average Horizontal (RotD50)", "Horizontal")
    assert len(bb06.path) == 2
    assert bb06.path[0].value == "Average Horizontal (RotD50)"
    assert bb06.path[-1].value == "Horizontal"

    # Test exception for unknown imt
    with pytest.raises(ValueError) as e:
        bb06.convertSigmasOnce(IMT("wrong"), 0)
    with pytest.raises(ValueError) as e:
        bb06.convertAmpsOnce(IMT("wrong"), [10.0], None, None)
    # Test exception for unknown imc
    with pytest.raises(ValueError) as e:
        bb06._verifyConversion("Wrong", imc_out=None)
    bb06.imc_out = "wrong"
    with pytest.raises(ValueError) as e:
        bb06.convertAmpsOnce(PGA(), [10.0], None, None)

    # Test that AVERAGE_HORIZONTAL returns 1 regardless of imt
    bb06 = BeyerBommer2006("Average horizontal", "Average Horizontal (RotD50)")
    denom = 1
    numer = 1
    result = np.asarray([10.0]) + np.log(numer / denom)
    returned1 = bb06.convertAmpsOnce(PGA(), [10.0], None, None)
    returned2 = bb06.convertAmpsOnce(PGV(), [10.0], None, None)
    returned3 = bb06.convertAmpsOnce(SA(0.3), [10.0], None, None)
    returned4 = bb06.convertAmpsOnce(SA(1.0), [10.0], None, None)
    assert result == returned1 == returned2 == returned3 == returned4
    ss = np.asarray([10])
    R1, C1 = 1, 0
    s1 = (ss ** 2 - C1 ** 2) / R1 ** 2
    R2 = np.asarray([1, 1, 1, 1])
    C2 = np.asarray([0.02, 0.02, 0.0241407224538, 0.03])
    imt_list = [PGA(), PGV(), SA(0.3), SA(1.0)]
    for idx, imt in enumerate(imt_list):
        target = np.sqrt(s1 * R2[idx] ** 2 + C2[idx] ** 2)
        returned = bb06.convertSigmasOnce(imt, ss)
        assert target == returned


if __name__ == "__main__":
    test_bb06()
