#!/usr/bin/env python

# stdlib imports
import logging
import os
import os.path
import pathlib

# third party imports
import numpy as np
from esi_utils_io.smcontainers import ShakeMapOutputContainer

# local imports
from shakemap.coremods.assemble import AssembleModule
from shakemap.coremods.model import ModelModule
from shakemap.coremods.plotregr import PlotRegr
from shakemap.coremods.xtestimage import XTestImage
from shakemap.coremods.xtestplot import XTestPlot
from shakemap.coremods.xtestplot_multi import XTestPlotMulti
from shakemap.coremods.xtestplot_spectra import XTestPlotSpectra
from shakemap.utils.config import get_config_paths, get_model_config

########################################################################
# Test the nullgmpe and the dummy correlation function as well as
# the two xtestplot functions
########################################################################

#
# Compute the bias (u_dB), the std of the bias (sigma_dW), the
# the conditional mean at the observation point (u_z), and the
# conditional std at the observation point (s_z) for the cases
# 8a-e
#
se = np.array([0.0, 0.75, 1.5, 3.0, 6.0])
sigma = 0.8
tau = 0.6
# New-style bias and MVN
s_w2w2_inv = 1.0 / (sigma**2 + se**2)
den = 1.0 / (1.0 + tau * s_w2w2_inv * tau)
num = tau * s_w2w2_inv * (1.0) * den
u_dB = tau * num
sigma_dW = np.sqrt(sigma**2 + tau**2 * den)
u_z = 0 + u_dB + sigma**2 * s_w2w2_inv * (1 - u_dB)
s_z = np.sqrt(
    sigma**2
    - sigma**2 * s_w2w2_inv * sigma**2
    + (tau - sigma**2 * s_w2w2_inv * tau) ** 2 * den
)

# omega = np.sqrt(sigma**2 / (sigma**2 + se**2))
# num = omega**2 / sigma**2
# den = 1.0 / ((1.0 / tau**2) + num)
# u_dB = num * den
# sigma_dW = np.sqrt(sigma**2 + den)
# u_z = u_dB + (1 - u_dB) * sigma_dW**2 / (sigma_dW**2 + se**2)
# s_z = np.sqrt(sigma_dW**2 * se**2 / (sigma_dW**2 + se**2))

# print('bias: ', u_dB)
# print('bias std: ', sigma_dW)
# print('u|z: ', u_z)
# print('s|z: ', s_z)
# exit()


def run_event(evid):
    logger = logging.getLogger()
    installpath, datapath = get_config_paths()
    eventpath = pathlib.Path(datapath) / evid / "current"
    global_config = get_model_config(installpath, eventpath, logger)
    old_pointsfile = global_config["interp"]["prediction_location"]["file"]
    old_pointsfile = pathlib.Path(old_pointsfile.replace("<INSTALL_DIR>", installpath))
    new_pointsfile = old_pointsfile.with_suffix(".csv")
    assemble = AssembleModule(evid, comment="Test comment.", points=new_pointsfile)
    assemble.execute()
    model = ModelModule(evid)
    model.execute()
    res_file = os.path.join(datapath, evid, "current", "products", "shake_result.hdf")
    oc = ShakeMapOutputContainer.load(res_file)
    imts = oc.getIMTs()
    imt = imts[0].split("/")[1]
    comps = oc.getComponents(imt)
    imtdict = oc.getIMTArrays(imt, comps[0])
    return imtdict


def test_verification_0001():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0001"
    try:
        imtdict = run_event(evid)
        assert np.allclose(np.zeros_like(imtdict["mean"]), imtdict["mean"])
        np.testing.assert_almost_equal(np.min(imtdict["std"]), 0)
        assert np.max(imtdict["std"]) > 0.8 and np.max(imtdict["std"]) < 1.0
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0002():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0002"
    try:
        imtdict = run_event(evid)
        assert np.allclose([np.min(imtdict["mean"])], [-1.0])
        assert np.allclose([np.max(imtdict["mean"])], [1.0])
        assert np.allclose([np.min(np.abs(imtdict["mean"]))], [0.0])
        np.testing.assert_almost_equal(np.min(imtdict["std"]), 0)
        assert np.max(imtdict["std"]) > 0.8 and np.max(imtdict["std"]) < 1.0
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0003():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0003"
    try:
        imtdict = run_event(evid)
        assert np.allclose([np.min(imtdict["mean"])], [0.36], atol=0.0001)
        assert np.allclose([np.max(imtdict["mean"])], [1.0])
        assert np.allclose([np.min(imtdict["std"])], [0], atol=6e-7)
        assert np.allclose([np.max(imtdict["std"])], [0.933], atol=0.0001)
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0004():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0004"
    try:
        imtdict = run_event(evid)
        assert np.allclose([np.min(imtdict["mean"])], [0.36], atol=0.0001)
        assert np.allclose([np.max(imtdict["mean"])], [1.0])
        assert np.allclose([np.min(imtdict["std"])], [0], atol=0.0001)
        assert np.allclose([np.max(imtdict["std"])], [0.933], atol=0.0001)
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0005():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0005"
    try:
        imtdict = run_event(evid)
        assert np.allclose(np.zeros_like(imtdict["mean"]), imtdict["mean"])
        assert np.allclose([np.min(imtdict["std"])], [0], atol=0.0001)
        assert np.allclose([np.max(imtdict["std"])], [0.933], atol=0.0001)
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0008a():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0008a"
    try:
        imtdict = run_event(evid)
        assert np.allclose([np.min(imtdict["mean"])], [u_dB[0]], atol=0.0001)
        assert np.allclose([np.max(imtdict["mean"])], [u_z[0]], atol=0.0001)
        assert np.allclose([np.min(imtdict["std"])], [s_z[0]], atol=0.0001)
        assert np.allclose([np.max(imtdict["std"])], [sigma_dW[0]], atol=0.0001)
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0008b():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0008b"
    try:
        imtdict = run_event(evid)
        assert np.allclose([np.min(imtdict["mean"])], [u_dB[1]], atol=0.0001)
        assert np.allclose([np.max(imtdict["mean"])], [u_z[1]], atol=0.0001)
        assert np.allclose([np.min(imtdict["std"])], [s_z[1]], atol=0.0001)
        assert np.allclose([np.max(imtdict["std"])], [sigma_dW[1]], atol=0.0001)
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0008c():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0008c"
    try:
        imtdict = run_event(evid)
        assert np.allclose([np.min(imtdict["mean"])], [u_dB[2]], atol=0.0001)
        assert np.allclose([np.max(imtdict["mean"])], [u_z[2]], atol=0.0001)
        assert np.allclose([np.min(imtdict["std"])], [s_z[2]], atol=0.0001)
        assert np.allclose([np.max(imtdict["std"])], [sigma_dW[2]], atol=0.0001)
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0008d():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0008d"
    try:
        imtdict = run_event(evid)
        assert np.allclose([np.min(imtdict["mean"])], [u_dB[3]], atol=0.0001)
        assert np.allclose([np.max(imtdict["mean"])], [u_z[3]], atol=0.0001)
        assert np.allclose([np.min(imtdict["std"])], [s_z[3]], atol=0.0001)
        assert np.allclose([np.max(imtdict["std"])], [sigma_dW[3]], atol=0.0001)
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def test_verification_0008e():
    installpath, datapath = get_config_paths()
    evid = "verification_test_0008e"
    try:
        imtdict = run_event(evid)
        assert np.allclose([np.min(imtdict["mean"])], [u_dB[4]], atol=0.0001)
        assert np.allclose([np.max(imtdict["mean"])], [u_z[4]], atol=0.0001)
        assert np.allclose([np.min(imtdict["std"])], [s_z[4]], atol=0.0001)
        assert np.allclose([np.max(imtdict["std"])], [sigma_dW[4]], atol=0.0001)
    finally:
        data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
        if os.path.isfile(data_file):
            os.remove(data_file)


def get_pointsfile(evid, installpath, datapath, logger):
    eventpath = pathlib.Path(datapath) / evid / "current"
    global_config = get_model_config(installpath, eventpath, logger)
    old_pointsfile = global_config["interp"]["prediction_location"]["file"]
    old_pointsfile = pathlib.Path(old_pointsfile.replace("<INSTALL_DIR>", installpath))
    new_pointsfile = old_pointsfile.with_suffix(".csv")
    return new_pointsfile


def test_verification():
    installpath, datapath = get_config_paths()

    logger = logging.getLogger()

    try:
        #
        # Test xtestplot on verification event 0006
        #
        evid = "verification_test_0006"
        new_pointsfile = get_pointsfile(evid, installpath, datapath, logger)
        assemble = AssembleModule(evid, comment="Test comment.", points=new_pointsfile)
        assemble.execute()
        model = ModelModule(evid)
        model.execute()
        plot = XTestPlot(evid)
        plot.execute()

        #
        # Test xtestplot_spectra on verification event 0007
        #
        evid = "verification_test_0007"
        new_pointsfile = get_pointsfile(evid, installpath, datapath, logger)
        assemble = AssembleModule(evid, comment="Test comment.", points=new_pointsfile)
        assemble.execute()
        model = ModelModule(evid)
        model.execute()
        plot = XTestPlotSpectra(evid)
        plot.execute()

        #
        # Test xtestimage on verification event 0011
        #
        evid = "verification_test_0011"
        assemble = AssembleModule(evid, comment="Test comment.")
        assemble.execute()
        model = ModelModule(evid)
        model.execute()
        plot = XTestImage(evid)
        plot.execute()
        regr = PlotRegr(evid)
        regr.execute()

        #
        # Test xtestplot_multi on event 0008x
        #
        for vt in ("8a", "8b", "8c", "8d", "8e"):
            evid = f"verification_test_000{vt}"
            new_pointsfile = get_pointsfile(evid, installpath, datapath, logger)
            assemble = AssembleModule(
                evid, comment="Test comment.", points=new_pointsfile
            )
            assemble.execute()
            model = ModelModule(f"verification_test_000{vt}")
            model.execute()
        plot = XTestPlotMulti("verification_test_0008")
        plot.execute()

    finally:
        data_file = os.path.join(
            datapath, "verification_test_0006", "current", "shake_data.hdf"
        )
        if os.path.isfile(data_file):
            os.remove(data_file)
        data_file = os.path.join(
            datapath, "verification_test_0007", "current", "shake_data.hdf"
        )
        if os.path.isfile(data_file):
            os.remove(data_file)
        data_file = os.path.join(
            datapath, "verification_test_0011", "current", "shake_data.hdf"
        )
        if os.path.isfile(data_file):
            os.remove(data_file)
        for vt in ("8a", "8b", "8c", "8d", "8e"):
            evid = f"verification_test_000{vt}"
            data_file = os.path.join(datapath, evid, "current", "shake_data.hdf")
            if os.path.isfile(data_file):
                os.remove(data_file)


if __name__ == "__main__":
    os.environ["CALLED_FROM_PYTEST"] = "True"
    test_verification_0001()
    test_verification_0002()
    test_verification_0003()
    test_verification_0004()
    test_verification_0005()
    test_verification_0008a()
    test_verification_0008b()
    test_verification_0008c()
    test_verification_0008d()
    test_verification_0008e()
    test_verification()
