#!/usr/bin/env python

# stdlib imports
import os.path
import sys

# third party imports
from openquake.hazardlib.geo.utils import OrthographicProjection
from openquake.hazardlib.gsim.abrahamson_2014 import AbrahamsonEtAl2014
from openquake.hazardlib.gsim.berge_thierry_2003 import BergeThierryEtAl2003SIGMA
import numpy as np
import pandas as pd
import pytest
import time

# local imports
from shakelib.distance import Distance
from shakelib.distance import get_distance
from shakelib.rupture.gc2 import _computeGC2
from shakelib.rupture.origin import Origin
from shakelib.rupture.point_rupture import PointRupture
from shakelib.rupture.quad_rupture import QuadRupture
from shakelib.sites import Sites
from impactutils.time.ancient_time import HistoricTime


do_tests = True

homedir = os.path.dirname(os.path.abspath(__file__))  # where is this script?
shakedir = os.path.abspath(os.path.join(homedir, "..", ".."))
sys.path.insert(0, shakedir)


def test_san_fernando():
    # This is a challenging rupture due to overlapping and discordant
    # segments, as brought up by Graeme Weatherill. Our initial
    # implementation put the origin on the wrong side of the rupture.
    x0 = np.array([7.1845, 7.8693])
    y0 = np.array([-10.3793, -16.2096])
    z0 = np.array([3.0000, 0.0000])
    x1 = np.array([-7.8506, -7.5856])
    y1 = np.array([-4.9073, -12.0682])
    z1 = np.array([3.0000, 0.0000])
    x2 = np.array([-4.6129, -5.5149])
    y2 = np.array([3.9887, -4.3408])
    z2 = np.array([16.0300, 8.0000])
    x3 = np.array([10.4222, 9.9400])
    y3 = np.array([-1.4833, -8.4823])
    z3 = np.array([16.0300, 8.0000])

    epilat = 34.44000
    epilon = -118.41000
    proj = OrthographicProjection(epilon - 1, epilon + 1, epilat + 1, epilat - 1)
    lon0, lat0 = proj(x0, y0, reverse=True)
    lon1, lat1 = proj(x1, y1, reverse=True)
    lon2, lat2 = proj(x2, y2, reverse=True)
    lon3, lat3 = proj(x3, y3, reverse=True)

    # Rupture requires an origin even when not used:
    origin = Origin(
        {
            "id": "test",
            "lat": 0,
            "lon": 0,
            "depth": 5.0,
            "mag": 7.0,
            "netid": "",
            "network": "",
            "locstring": "",
            "time": HistoricTime.utcfromtimestamp(int(time.time())),
        }
    )

    rup = QuadRupture.fromVertices(
        lon0, lat0, z0, lon1, lat1, z1, lon2, lat2, z2, lon3, lat3, z3, origin
    )
    # Make a origin object; most of the 'event' values don't matter
    event = {
        "lat": 0,
        "lon": 0,
        "depth": 0,
        "mag": 6.61,
        "id": "",
        "locstring": "",
        "type": "ALL",
        "netid": "",
        "network": "",
        "time": HistoricTime.utcfromtimestamp(int(time.time())),
    }
    origin = Origin(event)

    # Grid of sites
    buf = 0.25
    lat = np.linspace(np.nanmin(rup._lat) - buf, np.nanmax(rup._lat) + buf, 10)
    lon = np.linspace(np.nanmin(rup._lon) - buf, np.nanmax(rup._lon) + buf, 10)
    lons, lats = np.meshgrid(lon, lat)
    dep = np.zeros_like(lons)
    x, y = proj(lon, lat)
    rupx, rupy = proj(rup._lon[~np.isnan(rup._lon)], rup._lat[~np.isnan(rup._lat)])

    # Calculate U and T
    dtypes = ["U", "T"]
    dists = get_distance(dtypes, lats, lons, dep, rup)

    targetU = np.array(
        [
            [
                29.37395812,
                22.56039569,
                15.74545461,
                8.92543078,
                2.09723735,
                -4.73938823,
                -11.58093887,
                -18.42177264,
                -25.25743913,
                -32.08635501,
            ],
            [
                31.84149137,
                25.03129417,
                18.22007124,
                11.40292429,
                4.57583886,
                -2.26009972,
                -9.09790123,
                -15.92911065,
                -22.75071243,
                -29.56450963,
            ],
            [
                34.30623138,
                27.49382948,
                20.67774678,
                13.85111535,
                7.0115472,
                0.16942111,
                -6.65327488,
                -13.45181115,
                -20.24352643,
                -27.03530618,
            ],
            [
                36.78170249,
                29.96380633,
                23.1270492,
                16.23906653,
                9.32934682,
                2.41729624,
                -4.2732657,
                -10.94940844,
                -17.703852,
                -24.4792072,
            ],
            [
                39.29233805,
                32.49155866,
                25.68380903,
                18.73823089,
                12.08780156,
                5.99219619,
                -1.38387344,
                -8.28331275,
                -15.08759643,
                -21.87909368,
            ],
            [
                41.84662959,
                35.09745097,
                28.42432401,
                21.98993679,
                15.2994003,
                8.38037254,
                1.3900846,
                -5.5601922,
                -12.4250749,
                -19.24690137,
            ],
            [
                44.41552101,
                37.69652131,
                31.0257236,
                24.38573309,
                17.67059825,
                10.84688716,
                3.96604399,
                -2.920931,
                -9.78152208,
                -16.6132751,
            ],
            [
                46.97201328,
                40.2558351,
                33.55821495,
                26.85923974,
                20.12416451,
                13.33640001,
                6.50905851,
                -0.33349597,
                -7.17138975,
                -13.99568321,
            ],
            [
                49.51154107,
                42.79053584,
                36.07536907,
                29.35382731,
                22.61099757,
                15.83894006,
                9.04135415,
                2.22928601,
                -4.58574545,
                -11.3959888,
            ],
            [
                52.03832734,
                45.31289877,
                38.58842009,
                31.85764151,
                25.11309728,
                18.35066231,
                11.57145669,
                4.78070229,
                -2.01505508,
                -8.81029694,
            ],
        ]
    )
    np.testing.assert_allclose(dists["U"], targetU, atol=0.01)

    targetT = np.array(
        [
            [
                -40.32654805,
                -38.14066537,
                -35.95781299,
                -33.79265063,
                -31.65892948,
                -29.56075203,
                -27.48748112,
                -25.41823592,
                -23.33452174,
                -21.22822801,
            ],
            [
                -32.28894353,
                -30.06603457,
                -27.83163648,
                -25.61482279,
                -23.45367121,
                -21.36959238,
                -19.34738882,
                -17.33510593,
                -15.28949735,
                -13.20224592,
            ],
            [
                -24.30254163,
                -22.03532096,
                -19.70590091,
                -17.35907062,
                -15.10840929,
                -13.02682541,
                -11.13554925,
                -9.25705749,
                -7.26675455,
                -5.19396824,
            ],
            [
                -16.41306482,
                -14.1418547,
                -11.68888578,
                -8.9318195,
                -6.39939727,
                -4.10984325,
                -2.85061088,
                -1.29211846,
                0.68929792,
                2.78115216,
            ],
            [
                -8.63784529,
                -6.5089946,
                -4.32108309,
                -1.44275161,
                -0.05102145,
                -0.20890633,
                3.92700516,
                6.36977183,
                8.55572399,
                10.72128633,
            ],
            [
                -0.88135778,
                1.06766314,
                2.77955566,
                3.8241835,
                5.99212478,
                8.76823285,
                11.54715599,
                14.0961506,
                16.4200502,
                18.65346494,
            ],
            [
                6.98140207,
                8.91888936,
                10.77724993,
                12.6499521,
                14.79454638,
                17.18482779,
                19.63520498,
                22.03525644,
                24.35152986,
                26.60592498,
            ],
            [
                14.95635952,
                16.95134069,
                18.94768299,
                20.99811237,
                23.15975573,
                25.42700742,
                27.74302905,
                30.0547134,
                32.33583361,
                34.58421221,
            ],
            [
                22.9921068,
                25.0353212,
                27.09829391,
                29.20364631,
                31.3678744,
                33.58684524,
                35.8383652,
                38.09736043,
                40.34713771,
                42.58152772,
            ],
            [
                31.05186177,
                33.1252095,
                35.21960344,
                37.34488267,
                39.50633206,
                41.70076344,
                43.91762786,
                46.14415669,
                48.37021739,
                50.59029205,
            ],
        ]
    )
    np.testing.assert_allclose(dists["T"], targetT, atol=0.01)

    # new method:
    ddict = _computeGC2(rup, lons, lats, dep)
    np.testing.assert_allclose(ddict["T"], targetT, atol=0.01)
    np.testing.assert_allclose(ddict["U"], targetU, atol=0.01)


def test_exceptions():
    vs30file = os.path.join(homedir, "distance_data/Vs30_test.grd")
    cx = -118.2
    cy = 34.1
    dx = 0.0083
    dy = 0.0083
    xspan = 0.0083 * 5
    yspan = 0.0083 * 5
    site = Sites.fromCenter(
        cx, cy, xspan, yspan, dx, dy, vs30File=vs30file, padding=True, resample=False
    )
    # Make souce instance
    lat0 = np.array([34.1])
    lon0 = np.array([-118.2])
    lat1 = np.array([34.2])
    lon1 = np.array([-118.15])
    z = np.array([1.0])
    W = np.array([3.0])
    dip = np.array([30.0])

    # Rupture requires an origin even when not used:
    origin = Origin(
        {
            "id": "test",
            "lat": 0,
            "lon": 0,
            "depth": 5.0,
            "mag": 7.0,
            "netid": "",
            "network": "",
            "locstring": "",
            "time": HistoricTime.utcfromtimestamp(int(time.time())),
        }
    )
    rup = QuadRupture.fromTrace(lon0, lat0, lon1, lat1, z, W, dip, origin)

    event = {
        "lat": 34.1,
        "lon": -118.2,
        "depth": 1,
        "mag": 6,
        "id": "",
        "locstring": "",
        "mech": "RS",
        "rake": 90,
        "netid": "",
        "network": "",
        "time": HistoricTime.utcfromtimestamp(int(time.time())),
    }
    origin = Origin(event)

    gmpelist = ["Primate"]
    with pytest.raises(Exception) as e:  # noqa
        Distance.fromSites(gmpelist, origin, site, rup)

    gmpelist = [AbrahamsonEtAl2014()]
    sctx = site.getSitesContext()
    dist_types = ["repi", "rhypo", "rjb", "rrup", "rx", "ry", "ry0", "U", "V"]
    with pytest.raises(Exception) as e:  # noqa
        get_distance(dist_types, sctx.lats, sctx.lons, np.zeros_like(sctx.lons), rup)

    dist_types = ["repi", "rhypo", "rjb", "rrup", "rx", "ry", "ry0", "U", "T"]
    with pytest.raises(Exception) as e:  # noqa
        get_distance(
            dist_types,
            sctx.lats,
            sctx.lons[
                0:4,
            ],
            np.zeros_like(sctx.lons),
            rup,
        )
    # Exception when not a GMPE subclass
    with pytest.raises(Exception) as e:  # noqa
        Distance([None], [-118.2], [34.1], [1], rupture=None)


def test_distance_no_rupture():
    event = {
        "lat": 34.1,
        "lon": -118.2,
        "depth": 1,
        "mag": 6,
        "id": "",
        "locstring": "",
        "mech": "RS",
        "rake": 90,
        "netid": "",
        "network": "",
        "time": HistoricTime.utcfromtimestamp(int(time.time())),
    }
    origin = Origin(event)
    origin.setMechanism("ALL")
    # Make sites instance
    vs30file = os.path.join(homedir, "distance_data/Vs30_test.grd")
    cx = -118.2
    cy = 34.1
    dx = 0.0083
    dy = 0.0083
    xspan = 0.0083 * 5
    yspan = 0.0083 * 5
    site = Sites.fromCenter(
        cx, cy, xspan, yspan, dx, dy, vs30File=vs30file, padding=True, resample=False
    )
    # Make souce instance
    #  - Unknown/no tectonic region
    #  - Mech is ALL

    gmpe = AbrahamsonEtAl2014()
    rupture = PointRupture(origin)
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                1.19350211e00,
                1.01453734e00,
                8.94306248e-01,
                8.51431703e-01,
                8.94306248e-01,
                1.01453734e00,
                1.19350211e00,
            ],
            [
                9.23698454e-01,
                6.97204114e-01,
                5.32067867e-01,
                4.69137288e-01,
                5.32067867e-01,
                6.97204114e-01,
                9.23698454e-01,
            ],
            [
                7.28251778e-01,
                4.44114326e-01,
                2.60572550e-01,
                1.94977658e-01,
                2.60572550e-01,
                4.44114326e-01,
                7.28251778e-01,
            ],
            [
                6.54236979e-01,
                3.39249542e-01,
                1.57170497e-01,
                1.98278110e-05,
                1.57170497e-01,
                3.39249542e-01,
                6.54236979e-01,
            ],
            [
                7.28338531e-01,
                4.44167697e-01,
                2.60583985e-01,
                1.94977658e-01,
                2.60583985e-01,
                4.44167697e-01,
                7.28338531e-01,
            ],
            [
                9.23844143e-01,
                6.97283640e-01,
                5.32091716e-01,
                4.69137288e-01,
                5.32091716e-01,
                6.97283640e-01,
                9.23844143e-01,
            ],
            [
                1.19368104e00,
                1.01462773e00,
                8.94331130e-01,
                8.51431703e-01,
                8.94331130e-01,
                1.01462773e00,
                1.19368104e00,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                4.0129619,
                3.93137849,
                3.87656959,
                3.85702467,
                3.87656959,
                3.93137849,
                4.0129619,
            ],
            [
                3.88996841,
                3.78671803,
                3.71143853,
                3.68275081,
                3.71143853,
                3.78671803,
                3.88996841,
            ],
            [
                3.80087151,
                3.67134376,
                3.60166506,
                3.58311968,
                3.60166506,
                3.67134376,
                3.80087151,
            ],
            [
                3.7671309,
                3.62390909,
                3.57243062,
                3.53580973,
                3.57243062,
                3.62390909,
                3.7671309,
            ],
            [
                3.80091105,
                3.67136809,
                3.60166829,
                3.58311968,
                3.60166829,
                3.67136809,
                3.80091105,
            ],
            [
                3.89003482,
                3.78675428,
                3.7114494,
                3.68275081,
                3.7114494,
                3.78675428,
                3.89003482,
            ],
            [
                4.01304347,
                3.9314197,
                3.87658093,
                3.85702467,
                3.87658093,
                3.9314197,
                4.01304347,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))

    # Souce instance
    #  - Tectonic region unsupported
    #  - Mech is ALL
    origin._tectonic_region = "Volcano"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjbt = np.array(
        [
            [
                1.19350211e00,
                1.01453734e00,
                8.94306248e-01,
                8.51431703e-01,
                8.94306248e-01,
                1.01453734e00,
                1.19350211e00,
            ],
            [
                9.23698454e-01,
                6.97204114e-01,
                5.32067867e-01,
                4.69137288e-01,
                5.32067867e-01,
                6.97204114e-01,
                9.23698454e-01,
            ],
            [
                7.28251778e-01,
                4.44114326e-01,
                2.60572550e-01,
                1.94977658e-01,
                2.60572550e-01,
                4.44114326e-01,
                7.28251778e-01,
            ],
            [
                6.54236979e-01,
                3.39249542e-01,
                1.57170497e-01,
                1.98278110e-05,
                1.57170497e-01,
                3.39249542e-01,
                6.54236979e-01,
            ],
            [
                7.28338531e-01,
                4.44167697e-01,
                2.60583985e-01,
                1.94977658e-01,
                2.60583985e-01,
                4.44167697e-01,
                7.28338531e-01,
            ],
            [
                9.23844143e-01,
                6.97283640e-01,
                5.32091716e-01,
                4.69137288e-01,
                5.32091716e-01,
                6.97283640e-01,
                9.23844143e-01,
            ],
            [
                1.19368104e00,
                1.01462773e00,
                8.94331130e-01,
                8.51431703e-01,
                8.94331130e-01,
                1.01462773e00,
                1.19368104e00,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjbt, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    # Souce instance
    #  - Tectonic region: active
    #  - Mech is ALL

    origin.setMechanism("ALL")
    origin._tectonic_region = "Active Shallow Crust"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                1.19350211e00,
                1.01453734e00,
                8.94306248e-01,
                8.51431703e-01,
                8.94306248e-01,
                1.01453734e00,
                1.19350211e00,
            ],
            [
                9.23698454e-01,
                6.97204114e-01,
                5.32067867e-01,
                4.69137288e-01,
                5.32067867e-01,
                6.97204114e-01,
                9.23698454e-01,
            ],
            [
                7.28251778e-01,
                4.44114326e-01,
                2.60572550e-01,
                1.94977658e-01,
                2.60572550e-01,
                4.44114326e-01,
                7.28251778e-01,
            ],
            [
                6.54236979e-01,
                3.39249542e-01,
                1.57170497e-01,
                1.98278110e-05,
                1.57170497e-01,
                3.39249542e-01,
                6.54236979e-01,
            ],
            [
                7.28338531e-01,
                4.44167697e-01,
                2.60583985e-01,
                1.94977658e-01,
                2.60583985e-01,
                4.44167697e-01,
                7.28338531e-01,
            ],
            [
                9.23844143e-01,
                6.97283640e-01,
                5.32091716e-01,
                4.69137288e-01,
                5.32091716e-01,
                6.97283640e-01,
                9.23844143e-01,
            ],
            [
                1.19368104e00,
                1.01462773e00,
                8.94331130e-01,
                8.51431703e-01,
                8.94331130e-01,
                1.01462773e00,
                1.19368104e00,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                4.0129619,
                3.93137849,
                3.87656959,
                3.85702467,
                3.87656959,
                3.93137849,
                4.0129619,
            ],
            [
                3.88996841,
                3.78671803,
                3.71143853,
                3.68275081,
                3.71143853,
                3.78671803,
                3.88996841,
            ],
            [
                3.80087151,
                3.67134376,
                3.60166506,
                3.58311968,
                3.60166506,
                3.67134376,
                3.80087151,
            ],
            [
                3.7671309,
                3.62390909,
                3.57243062,
                3.53580973,
                3.57243062,
                3.62390909,
                3.7671309,
            ],
            [
                3.80091105,
                3.67136809,
                3.60166829,
                3.58311968,
                3.60166829,
                3.67136809,
                3.80091105,
            ],
            [
                3.89003482,
                3.78675428,
                3.7114494,
                3.68275081,
                3.7114494,
                3.78675428,
                3.89003482,
            ],
            [
                4.01304347,
                3.9314197,
                3.87658093,
                3.85702467,
                3.87658093,
                3.9314197,
                4.01304347,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))

    # Souce instance
    #  - Tectonic region: active
    #  - Mech is RS

    origin.setMechanism("RS")
    origin._tectonic_region = "Active Shallow Crust"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                7.76090807e-01,
                6.49225734e-01,
                5.63995966e-01,
                5.33602932e-01,
                5.63995966e-01,
                6.49225734e-01,
                7.76090807e-01,
            ],
            [
                5.84831599e-01,
                4.24273624e-01,
                3.07211355e-01,
                2.62600941e-01,
                3.07211355e-01,
                4.24273624e-01,
                5.84831599e-01,
            ],
            [
                4.46282784e-01,
                2.44862590e-01,
                1.32264468e-01,
                9.99797788e-02,
                1.32264468e-01,
                2.44862590e-01,
                4.46282784e-01,
            ],
            [
                3.93814955e-01,
                1.70987945e-01,
                8.13717378e-02,
                1.03958777e-05,
                8.13717378e-02,
                1.70987945e-01,
                3.93814955e-01,
            ],
            [
                4.46344282e-01,
                2.44900424e-01,
                1.32270097e-01,
                9.99797788e-02,
                1.32270097e-01,
                2.44900424e-01,
                4.46344282e-01,
            ],
            [
                5.84934876e-01,
                4.24329999e-01,
                3.07228262e-01,
                2.62600941e-01,
                3.07228262e-01,
                4.24329999e-01,
                5.84934876e-01,
            ],
            [
                7.76217650e-01,
                6.49289812e-01,
                5.64013604e-01,
                5.33602932e-01,
                5.64013604e-01,
                6.49289812e-01,
                7.76217650e-01,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                3.42235562,
                3.338452,
                3.28208435,
                3.26198358,
                3.28208435,
                3.338452,
                3.42235562,
            ],
            [
                3.29586422,
                3.18967743,
                3.112257,
                3.08275341,
                3.112257,
                3.18967743,
                3.29586422,
            ],
            [
                3.20423343,
                3.07102195,
                2.99912626,
                2.97986242,
                2.99912626,
                3.07102195,
                3.20423343,
            ],
            [
                3.16953325,
                3.02223204,
                2.96875925,
                2.92616469,
                2.96875925,
                3.02223204,
                3.16953325,
            ],
            [
                3.2042741,
                3.07104698,
                2.99912962,
                2.97986242,
                2.99912962,
                3.07104698,
                3.2042741,
            ],
            [
                3.29593253,
                3.18971471,
                3.11226818,
                3.08275341,
                3.11226818,
                3.18971471,
                3.29593253,
            ],
            [
                3.42243951,
                3.33849438,
                3.28209601,
                3.26198358,
                3.28209601,
                3.33849438,
                3.42243951,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))

    # Souce instance
    #  - Tectonic region: active
    #  - Mech is NM

    origin.setMechanism("NM")
    origin._tectonic_region = "Active Shallow Crust"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                8.32771820e-01,
                6.96170087e-01,
                6.04399092e-01,
                5.71673449e-01,
                6.04399092e-01,
                6.96170087e-01,
                8.32771820e-01,
            ],
            [
                6.26833822e-01,
                4.53953319e-01,
                3.27906737e-01,
                2.79872556e-01,
                3.27906737e-01,
                4.53953319e-01,
                6.26833822e-01,
            ],
            [
                4.77651641e-01,
                2.60772819e-01,
                1.38685718e-01,
                1.03235484e-01,
                1.38685718e-01,
                2.60772819e-01,
                4.77651641e-01,
            ],
            [
                4.21157003e-01,
                1.81206068e-01,
                8.28029065e-02,
                1.03958777e-05,
                8.28029065e-02,
                1.81206068e-01,
                4.21157003e-01,
            ],
            [
                4.77717859e-01,
                2.60813557e-01,
                1.38691898e-01,
                1.03235484e-01,
                1.38691898e-01,
                2.60813557e-01,
                4.77717859e-01,
            ],
            [
                6.26945025e-01,
                4.54014020e-01,
                3.27924941e-01,
                2.79872556e-01,
                3.27924941e-01,
                4.54014020e-01,
                6.26945025e-01,
            ],
            [
                8.32908398e-01,
                6.96239083e-01,
                6.04418084e-01,
                5.71673449e-01,
                6.04418084e-01,
                6.96239083e-01,
                8.32908398e-01,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                3.3192606,
                3.22072248,
                3.15452316,
                3.13091641,
                3.15452316,
                3.22072248,
                3.3192606,
            ],
            [
                3.17070653,
                3.0459986,
                2.95507447,
                2.92042485,
                2.95507447,
                3.0459986,
                3.17070653,
            ],
            [
                3.06309346,
                2.90664719,
                2.82107391,
                2.79752673,
                2.82107391,
                2.90664719,
                3.06309346,
            ],
            [
                3.02234086,
                2.84931729,
                2.78395476,
                2.73772697,
                2.78395476,
                2.84931729,
                3.02234086,
            ],
            [
                3.06314123,
                2.90667658,
                2.82107802,
                2.79752673,
                2.82107802,
                2.90667658,
                3.06314123,
            ],
            [
                3.17078675,
                3.04604238,
                2.9550876,
                2.92042485,
                2.9550876,
                3.04604238,
                3.17078675,
            ],
            [
                3.31935913,
                3.22077225,
                3.15453686,
                3.13091641,
                3.15453686,
                3.22077225,
                3.31935913,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))

    # Souce instance
    #  - Tectonic region: active
    #  - Mech is SS

    origin.setMechanism("SS")
    origin._tectonic_region = "Active Shallow Crust"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                1.95958776e00,
                1.66988434e00,
                1.47525745e00,
                1.40585328e00,
                1.47525745e00,
                1.66988434e00,
                1.95958776e00,
            ],
            [
                1.52283677e00,
                1.15619376e00,
                8.88875589e-01,
                7.87005240e-01,
                8.88875589e-01,
                1.15619376e00,
                1.52283677e00,
            ],
            [
                1.20645289e00,
                7.46498734e-01,
                4.23057706e-01,
                2.95503135e-01,
                4.23057706e-01,
                7.46498734e-01,
                1.20645289e00,
            ],
            [
                1.08663970e00,
                5.76051478e-01,
                2.21984054e-01,
                1.98278110e-05,
                2.21984054e-01,
                5.76051478e-01,
                1.08663970e00,
            ],
            [
                1.20659332e00,
                7.46585130e-01,
                4.23079943e-01,
                2.95503135e-01,
                4.23079943e-01,
                7.46585130e-01,
                1.20659332e00,
            ],
            [
                1.52307261e00,
                1.15632249e00,
                8.88914196e-01,
                7.87005240e-01,
                8.88914196e-01,
                1.15632249e00,
                1.52307261e00,
            ],
            [
                1.95987741e00,
                1.67003067e00,
                1.47529773e00,
                1.40585328e00,
                1.47529773e00,
                1.67003067e00,
                1.95987741e00,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                2.54969772,
                2.27038241,
                2.08273439,
                2.01581889,
                2.08273439,
                2.27038241,
                2.54969772,
            ],
            [
                2.12860763,
                1.77511159,
                1.51737884,
                1.41916133,
                1.51737884,
                1.77511159,
                2.12860763,
            ],
            [
                1.82356854,
                1.38010729,
                1.08693739,
                0.97911408,
                1.08693739,
                1.38010729,
                1.82356854,
            ],
            [
                1.70805158,
                1.21626476,
                0.91696757,
                0.78911491,
                0.91696757,
                1.21626476,
                1.70805158,
            ],
            [
                1.82370394,
                1.38019059,
                1.08695619,
                0.97911408,
                1.08695619,
                1.38019059,
                1.82370394,
            ],
            [
                2.12883501,
                1.77523571,
                1.51741606,
                1.41916133,
                1.51741606,
                1.77523571,
                2.12883501,
            ],
            [
                2.54997699,
                2.27052349,
                2.08277323,
                2.01581889,
                2.08277323,
                2.27052349,
                2.54997699,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))

    # Souce instance
    #  - Tectonic region: stable
    #  - Mech is all

    origin.setMechanism("ALL")
    origin._tectonic_region = "Stable Shallow Crust"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                1.49285078e00,
                1.26359361e00,
                1.10957536e00,
                1.05465228e00,
                1.10957536e00,
                1.26359361e00,
                1.49285078e00,
            ],
            [
                1.14722732e00,
                8.57083889e-01,
                6.45541307e-01,
                5.64926073e-01,
                6.45541307e-01,
                8.57083889e-01,
                1.14722732e00,
            ],
            [
                8.96856520e-01,
                5.32871196e-01,
                2.99662245e-01,
                2.17185537e-01,
                2.99662245e-01,
                5.32871196e-01,
                8.96856520e-01,
            ],
            [
                8.02042196e-01,
                3.98587924e-01,
                1.69648145e-01,
                1.98278110e-05,
                1.69648145e-01,
                3.98587924e-01,
                8.02042196e-01,
            ],
            [
                8.96967653e-01,
                5.32939565e-01,
                2.99676623e-01,
                2.17185537e-01,
                2.99676623e-01,
                5.32939565e-01,
                8.96967653e-01,
            ],
            [
                1.14741395e00,
                8.57185764e-01,
                6.45571858e-01,
                5.64926073e-01,
                6.45571858e-01,
                8.57185764e-01,
                1.14741395e00,
            ],
            [
                1.49308000e00,
                1.26370940e00,
                1.10960724e00,
                1.05465228e00,
                1.10960724e00,
                1.26370940e00,
                1.49308000e00,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                4.17967552,
                4.07332411,
                4.00187571,
                3.97639713,
                4.00187571,
                4.07332411,
                4.17967552,
            ],
            [
                4.01934229,
                3.88474601,
                3.78661232,
                3.74921526,
                3.78661232,
                3.88474601,
                4.01934229,
            ],
            [
                3.90319636,
                3.73434515,
                3.64558217,
                3.62308648,
                3.64558217,
                3.73434515,
                3.90319636,
            ],
            [
                3.85921241,
                3.67256434,
                3.61012056,
                3.57133422,
                3.61012056,
                3.67256434,
                3.85921241,
            ],
            [
                3.90324792,
                3.73437686,
                3.64558609,
                3.62308648,
                3.64558609,
                3.73437686,
                3.90324792,
            ],
            [
                4.01942887,
                3.88479327,
                3.7866265,
                3.74921526,
                3.7866265,
                3.88479327,
                4.01942887,
            ],
            [
                4.17978186,
                4.07337783,
                4.0018905,
                3.97639713,
                4.0018905,
                4.07337783,
                4.17978186,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))

    # Souce instance
    #  - Tectonic region: stable
    #  - Mech is RS

    origin.setMechanism("RS")
    origin._tectonic_region = "Stable Shallow Crust"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                1.11052523e00,
                9.25877479e-01,
                8.01828481e-01,
                7.57592465e-01,
                8.01828481e-01,
                9.25877479e-01,
                1.11052523e00,
            ],
            [
                8.32154030e-01,
                5.98467416e-01,
                4.28087307e-01,
                3.63158382e-01,
                4.28087307e-01,
                5.98467416e-01,
                8.32154030e-01,
            ],
            [
                6.30500991e-01,
                3.37340822e-01,
                1.69925286e-01,
                1.20068361e-01,
                1.69925286e-01,
                3.37340822e-01,
                6.30500991e-01,
            ],
            [
                5.54135870e-01,
                2.29725567e-01,
                9.13321474e-02,
                1.03958777e-05,
                9.13321474e-02,
                2.29725567e-01,
                5.54135870e-01,
            ],
            [
                6.30590499e-01,
                3.37395888e-01,
                1.69933978e-01,
                1.20068361e-01,
                1.69933978e-01,
                3.37395888e-01,
                6.30590499e-01,
            ],
            [
                8.32304345e-01,
                5.98549467e-01,
                4.28111914e-01,
                3.63158382e-01,
                4.28111914e-01,
                5.98549467e-01,
                8.32304345e-01,
            ],
            [
                1.11070985e00,
                9.25970743e-01,
                8.01854154e-01,
                7.57592465e-01,
                8.01854154e-01,
                9.25970743e-01,
                1.11070985e00,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                3.4885951,
                3.37216961,
                3.29395331,
                3.26606128,
                3.29395331,
                3.37216961,
                3.4885951,
            ],
            [
                3.3130744,
                3.16572856,
                3.05829921,
                3.01735974,
                3.05829921,
                3.16572856,
                3.3130744,
            ],
            [
                3.18592661,
                3.00108105,
                2.90341742,
                2.87839095,
                2.90341742,
                3.00108105,
                3.18592661,
            ],
            [
                3.1377763,
                2.9334351,
                2.86396637,
                2.81798622,
                2.86396637,
                2.9334351,
                3.1377763,
            ],
            [
                3.18598305,
                3.00111577,
                2.90342178,
                2.87839095,
                2.90342178,
                3.00111577,
                3.18598305,
            ],
            [
                3.31316918,
                3.16578029,
                3.05831472,
                3.01735974,
                3.05831472,
                3.16578029,
                3.31316918,
            ],
            [
                3.48871151,
                3.37222842,
                3.29396949,
                3.26606128,
                3.29396949,
                3.37222842,
                3.48871151,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))

    # Souce instance
    #  - Tectonic region: stable
    #  - Mech is NM

    origin.setMechanism("NM")
    origin._tectonic_region = "Stable Shallow Crust"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                1.12678662e00,
                9.39133949e-01,
                8.13066202e-01,
                7.68110298e-01,
                8.13066202e-01,
                9.39133949e-01,
                1.12678662e00,
            ],
            [
                8.43885262e-01,
                6.06395679e-01,
                4.33242838e-01,
                3.67257274e-01,
                4.33242838e-01,
                6.06395679e-01,
                8.43885262e-01,
            ],
            [
                6.38950562e-01,
                3.41019564e-01,
                1.70913434e-01,
                1.20272659e-01,
                1.70913434e-01,
                3.41019564e-01,
                6.38950562e-01,
            ],
            [
                5.61342691e-01,
                2.31653894e-01,
                9.10846554e-02,
                1.03958777e-05,
                9.10846554e-02,
                2.31653894e-01,
                5.61342691e-01,
            ],
            [
                6.39041527e-01,
                3.41075526e-01,
                1.70922263e-01,
                1.20272659e-01,
                1.70922263e-01,
                3.41075526e-01,
                6.39041527e-01,
            ],
            [
                8.44038024e-01,
                6.06479066e-01,
                4.33267846e-01,
                3.67257274e-01,
                4.33267846e-01,
                6.06479066e-01,
                8.44038024e-01,
            ],
            [
                1.12697424e00,
                9.39228730e-01,
                8.13092292e-01,
                7.68110298e-01,
                8.13092292e-01,
                9.39228730e-01,
                1.12697424e00,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                3.42781739,
                3.30181908,
                3.21717161,
                3.18698623,
                3.21717161,
                3.30181908,
                3.42781739,
            ],
            [
                3.23786489,
                3.07840387,
                2.96214139,
                2.91783576,
                2.96214139,
                3.07840387,
                3.23786489,
            ],
            [
                3.10026266,
                2.9002186,
                2.79362772,
                2.76581535,
                2.79362772,
                2.9002186,
                3.10026266,
            ],
            [
                3.0481533,
                2.82698693,
                2.74978504,
                2.70136713,
                2.74978504,
                2.82698693,
                3.0481533,
            ],
            [
                3.10032374,
                2.90025617,
                2.79363257,
                2.76581535,
                2.79363257,
                2.90025617,
                3.10032374,
            ],
            [
                3.23796746,
                3.07845986,
                2.96215818,
                2.91783576,
                2.96215818,
                3.07845986,
                3.23796746,
            ],
            [
                3.42794337,
                3.30188272,
                3.21718913,
                3.18698623,
                3.21718913,
                3.30188272,
                3.42794337,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))

    # Souce instance
    #  - Tectonic region: stable
    #  - Mech is SS

    origin.setMechanism("SS")
    origin._tectonic_region = "Stable Shallow Crust"
    dists = Distance.fromSites(gmpe, site, rupture)
    dctx = dists.getDistanceContext()

    rjb = np.array(
        [
            [
                1.80104893e00,
                1.52092305e00,
                1.33273049e00,
                1.26562081e00,
                1.33273049e00,
                1.52092305e00,
                1.80104893e00,
            ],
            [
                1.37873685e00,
                1.02421498e00,
                7.65734302e-01,
                6.67231768e-01,
                7.65734302e-01,
                1.02421498e00,
                1.37873685e00,
            ],
            [
                1.07281256e00,
                6.28064399e-01,
                3.42919369e-01,
                2.41987662e-01,
                3.42919369e-01,
                6.28064399e-01,
                1.07281256e00,
            ],
            [
                9.56960370e-01,
                4.63980672e-01,
                1.83813296e-01,
                1.98278110e-05,
                1.83813296e-01,
                4.63980672e-01,
                9.56960370e-01,
            ],
            [
                1.07294835e00,
                6.28147939e-01,
                3.42936965e-01,
                2.41987662e-01,
                3.42936965e-01,
                6.28147939e-01,
                1.07294835e00,
            ],
            [
                1.37896489e00,
                1.02433946e00,
                7.65771633e-01,
                6.67231768e-01,
                7.65771633e-01,
                1.02433946e00,
                1.37896489e00,
            ],
            [
                1.80132901e00,
                1.52106454e00,
                1.33276944e00,
                1.26562081e00,
                1.33276944e00,
                1.52106454e00,
                1.80132901e00,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rjb))

    rrup = np.array(
        [
            [
                2.85894272,
                2.62140075,
                2.46181667,
                2.4049088,
                2.46181667,
                2.62140075,
                2.85894272,
            ],
            [
                2.50082927,
                2.20020077,
                1.98101356,
                1.89748509,
                1.98101356,
                2.20020077,
                2.50082927,
            ],
            [
                2.24141069,
                1.86427183,
                1.65402932,
                1.59405522,
                1.65402932,
                1.86427183,
                2.24141069,
            ],
            [
                2.14317001,
                1.72596453,
                1.55948774,
                1.48557451,
                1.55948774,
                1.72596453,
                2.14317001,
            ],
            [
                2.24152584,
                1.86434267,
                1.65403978,
                1.59405522,
                1.65403978,
                1.86434267,
                2.24152584,
            ],
            [
                2.50102265,
                2.20030633,
                1.98104522,
                1.89748509,
                1.98104522,
                2.20030633,
                2.50102265,
            ],
            [
                2.85918022,
                2.62152073,
                2.46184969,
                2.4049088,
                2.46184969,
                2.62152073,
                2.85918022,
            ],
        ]
    )

    if do_tests is True:
        np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)
    else:
        print(repr(dctx.rrup))


def test_distance_from_sites_origin():
    # Make sites instance
    vs30file = os.path.join(homedir, "distance_data/Vs30_test.grd")
    cx = -118.2
    cy = 34.1
    dx = 0.0083
    dy = 0.0083
    xspan = 0.0083 * 5
    yspan = 0.0083 * 5
    site = Sites.fromCenter(
        cx, cy, xspan, yspan, dx, dy, vs30File=vs30file, padding=True, resample=False
    )
    # Make souce instance
    lat0 = np.array([34.1])
    lon0 = np.array([-118.2])
    lat1 = np.array([34.2])
    lon1 = np.array([-118.15])
    z = np.array([1.0])
    W = np.array([3.0])
    dip = np.array([30.0])

    event = {
        "lat": 34.1,
        "lon": -118.2,
        "depth": 1,
        "mag": 6,
        "id": "",
        "locstring": "",
        "mech": "ALL",
        "netid": "",
        "network": "",
        "time": HistoricTime.utcfromtimestamp(int(time.time())),
    }
    origin = Origin(event)

    rup = QuadRupture.fromTrace(lon0, lat0, lon1, lat1, z, W, dip, origin)
    gmpelist = [AbrahamsonEtAl2014(), BergeThierryEtAl2003SIGMA()]
    dists = Distance.fromSites(gmpelist, site, rup)
    dctx = dists.getDistanceContext()

    rhypo = np.array(
        [
            [
                3.74498133,
                3.32896405,
                3.05225679,
                2.95426722,
                3.05225679,
                3.32896405,
                3.74498133,
            ],
            [
                3.11965436,
                2.60558436,
                2.24124201,
                2.10583262,
                2.24124201,
                2.60558436,
                3.11965436,
            ],
            [
                2.67523213,
                2.05265767,
                1.564393,
                1.36331682,
                1.564393,
                2.05265767,
                2.67523213,
            ],
            [
                2.50973226,
                1.83166664,
                1.26045653,
                1.0,
                1.26045653,
                1.83166664,
                2.50973226,
            ],
            [
                2.67542717,
                2.05277065,
                1.56443006,
                1.36331682,
                1.56443006,
                2.05277065,
                2.67542717,
            ],
            [
                3.11998886,
                2.60576236,
                2.24129374,
                2.10583262,
                2.24129374,
                2.60576236,
                3.11998886,
            ],
            [
                3.74539929,
                3.32917303,
                3.05231378,
                2.95426722,
                3.05231378,
                3.32917303,
                3.74539929,
            ],
        ]
    )
    np.testing.assert_allclose(rhypo, dctx.rhypo, rtol=0, atol=0.01)

    rx = np.array(
        [
            [
                -3.18894050e00,
                -2.48001769e00,
                -1.77111874e00,
                -1.06224366e00,
                -3.53392480e-01,
                3.55434794e-01,
                1.06423815e00,
            ],
            [
                -2.83506890e00,
                -2.12607622e00,
                -1.41710740e00,
                -7.08162466e-01,
                7.58576362e-04,
                7.09655709e-01,
                1.41852892e00,
            ],
            [
                -2.48119723e00,
                -1.77213470e00,
                -1.06309603e00,
                -3.54081243e-01,
                3.54909645e-01,
                1.06387662e00,
                1.77281967e00,
            ],
            [
                -2.12732550e00,
                -1.41819312e00,
                -7.09084619e-01,
                2.56774082e-12,
                7.09060719e-01,
                1.41809752e00,
                2.12711040e00,
            ],
            [
                -1.77345370e00,
                -1.06425151e00,
                -3.55073182e-01,
                3.54081255e-01,
                1.06321179e00,
                1.77231841e00,
                2.48140110e00,
            ],
            [
                -1.41958186e00,
                -7.10309855e-01,
                -1.06172493e-03,
                7.08162516e-01,
                1.41736285e00,
                2.12653927e00,
                2.83569175e00,
            ],
            [
                -1.06570997e00,
                -3.56368176e-01,
                3.52949744e-01,
                1.06224377e00,
                1.77151390e00,
                2.48076010e00,
                3.18998236e00,
            ],
        ]
    )

    np.testing.assert_allclose(rx, dctx.rx, rtol=0, atol=0.01)

    rjb = np.array(
        [
            [
                3.19372137e00,
                2.48373511e00,
                1.77377308e00,
                1.06383562e00,
                3.53925643e-01,
                2.25816823e-03,
                2.45009861e-03,
            ],
            [
                2.83931844e00,
                2.12926243e00,
                1.41923064e00,
                7.09223517e-01,
                1.57594916e-03,
                1.86044244e-03,
                2.05239165e-03,
            ],
            [
                2.48510934e00,
                1.77479025e00,
                1.06468863e00,
                3.54611655e-01,
                1.04375185e-03,
                1.32827303e-03,
                1.52024106e-03,
            ],
            [
                2.30690967e00,
                1.53793979e00,
                7.68969896e-01,
                5.88918451e-12,
                3.77111295e-04,
                6.61660373e-04,
                8.53647223e-04,
            ],
            [
                2.48531877e00,
                1.79442084e00,
                1.20242597e00,
                8.54793253e-01,
                5.62052963e-01,
                2.69254693e-01,
                5.26105100e-05,
            ],
            [
                2.95646628e00,
                2.40489915e00,
                2.00231070e00,
                1.70958533e00,
                1.41681634e00,
                1.12398937e00,
                8.63761551e-01,
            ],
            [
                3.60741953e00,
                3.17112489e00,
                2.85711592e00,
                2.56437623e00,
                2.27157856e00,
                1.97872291e00,
                1.78518260e00,
            ],
        ]
    )

    np.testing.assert_allclose(rjb, dctx.rjb, rtol=0, atol=0.01)

    ry0 = np.array(
        [
            [
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
            ],
            [
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
            ],
            [
                2.29490054e-02,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
            ],
            [
                8.79341006e-01,
                5.86285236e-01,
                2.93171565e-01,
                6.21003581e-12,
                0.00000000e00,
                0.00000000e00,
                0.00000000e00,
            ],
            [
                1.73573289e00,
                1.44264826e00,
                1.14950573e00,
                8.56305300e-01,
                5.63046975e-01,
                2.69730762e-01,
                0.00000000e00,
            ],
            [
                2.59212463e00,
                2.29901116e00,
                2.00583977e00,
                1.71261048e00,
                1.41932329e00,
                1.12597821e00,
                8.32575235e-01,
            ],
            [
                3.44851622e00,
                3.15537391e00,
                2.86217367e00,
                2.56891553e00,
                2.27559947e00,
                1.98222553e00,
                1.68879368e00,
            ],
        ]
    )

    np.testing.assert_allclose(ry0, dctx.ry0, rtol=0, atol=0.01)

    rrup = np.array(
        [
            [
                3.34678672,
                2.67788811,
                2.03697073,
                1.46129187,
                1.06271102,
                1.06352692,
                1.40073832,
            ],
            [
                3.01030105,
                2.3526499,
                1.73673635,
                1.22706347,
                1.00157564,
                1.22283363,
                1.57764099,
            ],
            [
                2.67858182,
                2.03712377,
                1.46095502,
                1.06170931,
                1.06220616,
                1.39958479,
                1.75442695,
            ],
            [2.51415965, 1.8343632, 1.26143652, 1.0, 1.2212501, 1.57621925, 1.9310962],
            [
                2.67877609,
                2.05412785,
                1.56384179,
                1.3617346,
                1.50608502,
                1.77308319,
                2.10764873,
            ],
            [
                3.12078859,
                2.6043486,
                2.23799413,
                2.09885629,
                2.11696797,
                2.23191013,
                2.4299612,
            ],
            [
                3.74318473,
                3.32482368,
                3.04635272,
                2.9183523,
                2.86659485,
                2.88815116,
                2.98141559,
            ],
        ]
    )

    np.testing.assert_allclose(rrup, dctx.rrup, rtol=0, atol=0.01)


def test_chichi_with_get_distance():
    # read in rupture file
    f = os.path.join(homedir, "distance_data/0137A.POL")
    i0 = np.arange(0, 9 * 11 * 3, 11)
    i1 = i0 + 10
    cs = list(zip(i0, i1))
    df = pd.read_fwf(f, cs, skiprows=2, nrows=5, header=None)
    mat = df.values
    ix = np.arange(0, 9 * 3, 3)
    iy = ix + 1
    iz = ix + 2
    x0 = mat[0, ix]
    x1 = mat[1, ix]
    x2 = mat[2, ix]
    x3 = mat[3, ix]
    y0 = mat[0, iy]
    y1 = mat[1, iy]
    y2 = mat[2, iy]
    y3 = mat[3, iy]
    # Depth, positive down
    z0 = np.abs(mat[0, iz])
    z1 = np.abs(mat[1, iz])
    z2 = np.abs(mat[2, iz])
    z3 = np.abs(mat[3, iz])
    epilat = 23.85
    epilon = 120.82
    proj = OrthographicProjection(epilon - 1, epilon + 1, epilat + 1, epilat - 1)
    lon0, lat0 = proj(x0, y0, reverse=True)
    lon1, lat1 = proj(x1, y1, reverse=True)
    lon2, lat2 = proj(x2, y2, reverse=True)
    lon3, lat3 = proj(x3, y3, reverse=True)
    # event information doesn't matter except hypocenter
    event = {
        "lat": 23.85,
        "lon": 120.82,
        "depth": 8,
        "mag": 7.62,
        "id": "",
        "locstring": "",
        "mech": "ALL",
        "netid": "",
        "network": "",
        "time": HistoricTime.utcfromtimestamp(int(time.time())),
    }
    origin = Origin(event)
    rup = QuadRupture.fromVertices(
        lon0, lat0, z0, lon1, lat1, z1, lon2, lat2, z2, lon3, lat3, z3, origin
    )

    # Get NGA distances
    distfile = os.path.join(homedir, "distance_data/NGAW2_distances.csv")
    df = pd.read_csv(distfile)
    df2 = df.loc[df["EQID"] == 137]
    slat = df2["Station Latitude"].values
    slon = df2["Station Longitude"].values
    sdep = np.zeros(slat.shape)
    nga_repi = df2["EpiD (km)"].values
    nga_rhypo = df2["HypD (km)"].values
    nga_rrup = df2["ClstD (km)"].values
    nga_rjb = df2["Joyner-Boore Dist. (km)"].values
    nga_rx = df2["T"].values
    nga_T = df2["T"].values
    nga_U = df2["U"].values
    test_ry = np.array(
        [
            -49.25445446,
            -76.26871272,
            -37.1288192,
            -53.47792996,
            -50.30711637,
            -63.96322125,
            -61.01988704,
            -81.2001781,
            -76.00646939,
            -74.39038054,
            -92.23617124,
            -90.66976945,
            -89.68551411,
            -102.98798328,
            -114.70036085,
            -29.83636082,
            -28.50133134,
            -27.86922916,
            -36.00619214,
            -44.68826209,
            -47.64580208,
            -53.92619079,
            -59.11962858,
            -55.90584822,
            -55.00772025,
            -48.81756715,
            -59.27542007,
            -62.13633659,
            -70.0673351,
            -75.96977638,
            -61.6959293,
            -60.34564074,
            -81.49792285,
            -78.75933138,
            -80.80533738,
            -85.24473008,
            -94.07519297,
            -93.75010471,
            -96.87089883,
            -100.06112271,
            -98.86980873,
            -95.92330113,
            -107.44086722,
            -119.1065369,
            -120.60405905,
            -113.42995442,
            -115.94930662,
            -115.2398216,
            -107.37840927,
            -49.25445446,
            -48.78386688,
            -108.49133002,
            -88.03303353,
            -44.66653428,
            -81.04476548,
            -38.26801619,
            -70.51178983,
            -69.15679931,
            -74.74562139,
            -86.51133446,
            -27.62153029,
            -48.33279375,
            -30.0808298,
            -113.98345018,
            -97.96609537,
            -87.9863122,
            -39.45970018,
            -80.1387617,
            -42.27121388,
            -82.05027834,
            -81.55987067,
            -81.55987067,
            -107.25255717,
            67.62695516,
            -3.27797047,
            -197.98554369,
            82.30996151,
            18.42180605,
            -22.88851072,
            -35.75245916,
            -19.54788146,
            -18.19780517,
            19.85077702,
            20.33310282,
            19.95448398,
            20.55508903,
            18.17428572,
            17.87997374,
            16.97323804,
            16.0025885,
            13.88001846,
            18.42180605,
            -3.27797047,
            51.43098894,
            28.97695533,
            -53.20579538,
            38.7537468,
            33.48878882,
            26.25189111,
            22.54251612,
            13.37141837,
            -5.80928302,
            -6.68056794,
            -14.50860117,
            -15.23992093,
            -27.63281952,
            -11.66075049,
            -36.94595337,
            -40.97168031,
            -41.2814342,
            -48.64456898,
            -61.55777751,
            -11.15038984,
            -17.16482959,
            55.84202839,
            36.78540588,
            21.18550074,
            19.14658833,
            19.22680282,
            5.76327358,
            -47.45309937,
            -44.33194991,
            -55.15852372,
            37.33066096,
            37.64135657,
            14.31598698,
            4.60495737,
            6.87107021,
            18.42180605,
            113.59285783,
            109.06420877,
            104.23416509,
            99.21599973,
            95.25204545,
            90.29487934,
            86.26977557,
            95.28705209,
            87.12907925,
            101.40561896,
            96.68858152,
            92.90287952,
            100.36659012,
            97.19448577,
            92.8627461,
            85.01448355,
            93.36767736,
            96.90824009,
            86.48002825,
            88.71037964,
            106.17282325,
            102.56142319,
            97.60004093,
            99.61798574,
            97.36337239,
            94.22000798,
            86.99488734,
            90.05981676,
            90.51189502,
            100.7166391,
            100.31931988,
            67.62695516,
            94.15062409,
            87.77053675,
            124.21806013,
            99.23108884,
            101.48199452,
            92.63771423,
            78.88723272,
            72.7261356,
            80.58682246,
            73.30258213,
            70.20783518,
            60.57963211,
            -87.72265602,
            -148.10933308,
            -150.41334959,
            -144.12558375,
            -145.5625388,
            -132.09479688,
            -135.12980144,
            -121.10883695,
            -143.75755221,
            -117.73616176,
            -115.28563276,
            -138.79652905,
            -143.10405603,
            -151.78419035,
            -159.75299736,
            -149.69457229,
            -175.20332448,
            -181.00970647,
            -188.86536942,
            -176.88178468,
            -194.20978527,
            -204.54944453,
            -161.04413103,
            -197.98554369,
            -96.74089367,
            -133.49237232,
            -84.71198922,
            -164.97719097,
            -202.48241157,
            -74.54550169,
            -147.37402934,
            -144.64074441,
            -147.94282804,
            -122.80976842,
            -133.1671346,
            -136.3051809,
            -113.93174768,
            -151.02125407,
            -146.5198829,
            -156.19720713,
            -126.06138725,
            -131.44422964,
            -197.62591198,
            -204.42320856,
            -149.84576063,
            -121.56474664,
            -130.99947339,
            -148.41767074,
            -145.28448367,
            104.58903799,
            82.1649906,
            67.69977397,
            39.46989193,
            -69.00949731,
            -133.49237232,
            -128.264754,
            -84.71198922,
            -108.49133002,
            119.86128724,
            122.73556155,
            126.28254009,
            125.12436373,
            123.32498578,
            123.8337768,
            121.39931427,
            121.48412837,
            122.03669249,
            122.59675818,
            119.54338365,
            120.33961222,
            120.69581745,
            116.96928355,
            117.6687724,
            116.62277942,
            115.39650689,
            112.60751523,
            109.82643069,
            108.2500678,
            130.9143614,
            126.50049543,
            112.76229057,
            132.76840098,
            107.27099883,
            128.16063464,
            123.83157143,
            120.46711628,
            112.55756637,
            135.59953867,
            136.66138116,
            136.98573162,
            134.04528777,
            116.27744752,
            129.2794577,
            119.13550981,
            124.67196321,
            130.9728774,
            130.9039439,
            128.70028371,
            130.04592892,
            140.21819548,
            140.60370422,
            113.37585901,
            123.21523323,
            123.88149248,
            128.56894995,
            128.45186255,
            118.74080853,
            126.71189149,
            119.79833338,
            130.00866791,
            -160.01242472,
            13.55424709,
            110.26938756,
            97.71987778,
            110.93671325,
            108.71965725,
            105.03432063,
            106.36049687,
            99.27569343,
            115.06168146,
            77.00378531,
            81.50139192,
            92.15605815,
            79.94311644,
            83.16892433,
            52.23389149,
            50.97110177,
            67.95167063,
            63.43930833,
            40.20494692,
            43.22936492,
            47.21513635,
            38.94380012,
            53.85489136,
            56.69935207,
            48.07036522,
            64.46887891,
            14.98020647,
            17.35046801,
            16.15236633,
            14.41062231,
            19.99605739,
            18.31076661,
            15.07058247,
            12.34339267,
            13.57621451,
            14.72685201,
            22.04539325,
            20.47982142,
            9.66768974,
            8.05139052,
            29.22924869,
            3.75876894,
            7.8610467,
            29.20272495,
            15.19325822,
            -2.38981899,
            5.58349359,
            -0.62239018,
            -4.38178769,
            -11.43651893,
            -20.07048519,
            -16.0588668,
            82.30996151,
            13.55424709,
            104.49355303,
            -11.29628168,
            82.1649906,
            34.22207039,
            38.08490923,
            -10.15855131,
            111.0308369,
            81.78397481,
            73.56334665,
            81.27164139,
            74.55979012,
            16.08437955,
            23.8203941,
            24.68836209,
            28.73767914,
            21.06714416,
            19.44159522,
            4.62135887,
            3.41771413,
            5.051121,
            -6.81834189,
            6.40341853,
            -0.35693923,
            -17.74409367,
            -8.91759817,
            -18.05278804,
            7.70695248,
            -5.52733835,
            -16.02924961,
            -4.54310111,
            -22.84234773,
            -1.71908199,
            39.46989193,
            -14.74007542,
            23.59992543,
            -10.49966883,
            -11.47733869,
            -22.8200901,
            -9.72486483,
            95.96997763,
            -115.36487081,
            -52.88924268,
            -90.2275069,
            -132.22657274,
            -100.52455976,
            -115.24052939,
            -113.84482359,
            -114.41088165,
            -114.63386688,
            -115.92829006,
            -117.52597227,
            -114.49770514,
            -114.46881502,
            -76.26871272,
            -115.36487081,
            -160.01242472,
            -110.6429636,
            -77.47722955,
            -80.24672646,
            -85.90422427,
            -94.92075147,
            -102.44309541,
            -106.23741455,
            -111.56110193,
            -115.13402727,
            -48.64043046,
            -60.86151946,
            -66.52137871,
            -110.04628212,
            -75.27694696,
            -78.87041369,
            -88.08700161,
            -90.18844188,
            -93.65776393,
            -92.58976279,
            -107.31364843,
            -115.04064471,
            -125.98500718,
            -75.9341032,
            -39.45970018,
            -14.74007542,
            -23.16835763,
        ]
    )
    test_ry0 = np.array(
        [
            5.38783354,
            32.4020918,
            0.0,
            9.61130904,
            6.44049545,
            20.09660033,
            17.15326613,
            37.33355718,
            32.13984847,
            30.52375962,
            48.36955032,
            46.80314854,
            45.81889319,
            59.12136236,
            70.83373993,
            0.0,
            0.0,
            0.0,
            0.0,
            0.82164117,
            3.77918116,
            10.05956987,
            15.25300766,
            12.0392273,
            11.14109933,
            4.95094623,
            15.40879915,
            18.26971567,
            26.20071419,
            32.10315546,
            17.82930838,
            16.47901983,
            37.63130193,
            34.89271046,
            36.93871646,
            41.37810916,
            50.20857205,
            49.88348379,
            53.00427791,
            56.19450179,
            55.00318781,
            52.05668021,
            63.5742463,
            75.23991598,
            76.73743813,
            69.5633335,
            72.0826857,
            71.37320068,
            63.51178836,
            5.38783354,
            4.91724596,
            64.6247091,
            44.16641261,
            0.79991336,
            37.17814456,
            0.0,
            26.64516892,
            25.2901784,
            30.87900047,
            42.64471355,
            0.0,
            4.46617283,
            0.0,
            70.11682926,
            54.09947445,
            44.11969128,
            0.0,
            36.27214079,
            0.0,
            38.18365743,
            37.69324975,
            37.69324975,
            63.38593626,
            31.95985109,
            0.0,
            154.11892278,
            46.64285745,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            15.76388487,
            0.0,
            9.33917446,
            3.08664273,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            4.77794806,
            17.69115659,
            0.0,
            0.0,
            20.17492433,
            1.11830182,
            0.0,
            0.0,
            0.0,
            0.0,
            3.58647845,
            0.46532899,
            11.2919028,
            1.6635569,
            1.97425251,
            0.0,
            0.0,
            0.0,
            0.0,
            77.92575377,
            73.39710471,
            68.56706103,
            63.54889567,
            59.58494138,
            54.62777528,
            50.6026715,
            59.61994802,
            51.46197518,
            65.7385149,
            61.02147746,
            57.23577546,
            64.69948606,
            61.52738171,
            57.19564204,
            49.34737949,
            57.7005733,
            61.24113602,
            50.81292419,
            53.04327558,
            70.50571919,
            66.89431913,
            61.93293686,
            63.95088168,
            61.69626833,
            58.55290391,
            51.32778327,
            54.3927127,
            54.84479095,
            65.04953504,
            64.65221582,
            31.95985109,
            58.48352003,
            52.10343269,
            88.55095607,
            63.56398477,
            65.81489046,
            56.97061016,
            43.22012866,
            37.05903154,
            44.9197184,
            37.63547806,
            34.54073112,
            24.91252804,
            43.85603511,
            104.24271216,
            106.54672867,
            100.25896283,
            101.69591788,
            88.22817597,
            91.26318052,
            77.24221603,
            99.89093129,
            73.86954084,
            71.41901185,
            94.92990813,
            99.23743511,
            107.91756944,
            115.88637645,
            105.82795138,
            131.33670356,
            137.14308555,
            144.9987485,
            133.01516376,
            150.34316435,
            160.68282361,
            117.17751011,
            154.11892278,
            52.87427275,
            89.6257514,
            40.8453683,
            121.11057005,
            158.61579065,
            30.67888078,
            103.50740842,
            100.77412349,
            104.07620713,
            78.9431475,
            89.30051368,
            92.43855998,
            70.06512676,
            107.15463315,
            102.65326198,
            112.33058622,
            82.19476634,
            87.57760872,
            153.75929106,
            160.55658764,
            105.97913971,
            77.69812572,
            87.13285248,
            104.55104982,
            101.41786275,
            68.92193392,
            46.49788654,
            32.0326699,
            3.80278787,
            25.14287639,
            89.6257514,
            84.39813309,
            40.8453683,
            64.6247091,
            84.19418317,
            87.06845748,
            90.61543602,
            89.45725966,
            87.65788171,
            88.16667274,
            85.73221021,
            85.81702431,
            86.36958842,
            86.92965411,
            83.87627959,
            84.67250815,
            85.02871339,
            81.30217949,
            82.00166833,
            80.95567535,
            79.72940282,
            76.94041117,
            74.15932662,
            72.58296373,
            95.24725733,
            90.83339137,
            77.0951865,
            97.10129692,
            71.60389476,
            92.49353057,
            88.16446736,
            84.80001222,
            76.89046231,
            99.93243461,
            100.9942771,
            101.31862755,
            98.37818371,
            80.61034346,
            93.61235363,
            83.46840575,
            89.00485915,
            95.30577334,
            95.23683984,
            93.03317965,
            94.37882485,
            104.55109142,
            104.93660016,
            77.70875494,
            87.54812917,
            88.21438842,
            92.90184589,
            92.78475848,
            83.07370447,
            91.04478743,
            84.13122931,
            94.34156384,
            116.14580381,
            0.0,
            74.60228349,
            62.05277372,
            75.26960919,
            73.05255319,
            69.36721657,
            70.69339281,
            63.60858937,
            79.3945774,
            41.33668124,
            45.83428785,
            56.48895409,
            44.27601238,
            47.50182027,
            16.56678743,
            15.30399771,
            32.28456656,
            27.77220427,
            4.53784286,
            7.56226086,
            11.54803229,
            3.27669605,
            18.1877873,
            21.032248,
            12.40326116,
            28.80177485,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            46.64285745,
            0.0,
            68.82644897,
            0.0,
            46.49788654,
            0.0,
            2.41780516,
            0.0,
            75.36373283,
            46.11687074,
            37.89624258,
            45.60453732,
            38.89268605,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            3.80278787,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            60.30287357,
            71.49824989,
            9.02262176,
            46.36088598,
            88.35995182,
            56.65793884,
            71.37390848,
            69.97820268,
            70.54426073,
            70.76724596,
            72.06166914,
            73.65935135,
            70.63108422,
            70.6021941,
            32.4020918,
            71.49824989,
            116.14580381,
            66.77634268,
            33.61060864,
            36.38010555,
            42.03760335,
            51.05413055,
            58.57647449,
            62.37079364,
            67.69448101,
            71.26740635,
            4.77380954,
            16.99489854,
            22.65475779,
            66.1796612,
            31.41032604,
            35.00379277,
            44.22038069,
            46.32182096,
            49.79114301,
            48.72314188,
            63.44702751,
            71.1740238,
            82.11838626,
            32.06748228,
            0.0,
            0.0,
            0.0,
        ]
    )

    dist_types = ["repi", "rhypo", "rjb", "rrup", "rx", "ry", "ry0", "U", "T"]
    dists = get_distance(dist_types, slat, slon, sdep, rup)

    np.testing.assert_allclose(nga_repi, dists["repi"], rtol=0, atol=2)

    np.testing.assert_allclose(nga_rhypo, dists["rhypo"], rtol=0, atol=2)

    np.testing.assert_allclose(nga_rjb, dists["rjb"], rtol=0, atol=2)

    np.testing.assert_allclose(nga_rrup, dists["rrup"], rtol=0, atol=2)

    np.testing.assert_allclose(nga_rx, dists["rx"], rtol=0, atol=2)

    np.testing.assert_allclose(test_ry, dists["ry"], rtol=0, atol=2)

    np.testing.assert_allclose(test_ry0, dists["ry0"], rtol=0, atol=2)

    np.testing.assert_allclose(nga_U, dists["U"], rtol=0, atol=6)

    np.testing.assert_allclose(nga_T, dists["T"], rtol=0, atol=2)


if __name__ == "__main__":
    test_san_fernando()
    test_exceptions()
    test_distance_no_rupture()
    test_distance_from_sites_origin()
    test_chichi_with_get_distance()
