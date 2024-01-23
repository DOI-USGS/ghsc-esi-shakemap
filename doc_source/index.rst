.. _manual_4_title_page:

.. ShakeMap Manual documentation master file, created by
   sphinx-quickstart on Thu Nov 12 12:58:36 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

=================
ShakeMap 4 Manual
=================

                                                                               
**written by: C. Bruce Worden, Eric M. Thompson, Michael G. Hearne,            
and David J. Wald**                                                            


This online ShakeMap Manual (:ref:`Worden et al., 2020 <worden2020>`), is 
for ShakeMap version 4. Version 4 is the official, supported version of
ShakeMap and all earlier versions are now deprecated. This manual supersedes
all other versions of the ShakeMap Manual, including the ShakeMap 3.5 Manual
(both printed and online) and the USGS Techniques and Methods 
document (508)12-A1.


`ShakeMap® <http://earthquake.usgs.gov/shakemap/>`_, 
developed by the U.S. Geological Survey (USGS), facilitates communication of 
earthquake information beyond just magnitude and location. By rapidly mapping out 
earthquake ground motions, ShakeMap portrays the distribution and severity of shaking. 
This information is critical for gauging the extent of the areas affected, determining which areas 
are potentially hardest hit, and allowing for rapid estimation of losses. Key to 
ShakeMap's success, algorithms were developed that take advantage of any high-quality 
recorded ground motions---and any available macroseismic intensity data---to provide 
ground-truth constraints on shaking. Yet ShakeMap also utilizes best practices
for both interpolating recordings and---critically---providing
event-specific estimates of shaking in areas where observations are sparse
or nonexistent. Thus, ShakeMap portrays the best possible description of
shaking by employing a combination of recorded and estimated shaking values. 

This Manual provides background on technical aspects of ShakeMap including: 1) information on 
the wide range of products and formats ShakeMap produces, 2) the uses of these products, 
and 3) guidance for ShakeMap developers and operators. 

Readers interested in understanding the way 
ShakeMaps works can navigate to the :ref:`technical-guide-4`. Those who
want to use ShakeMap products and understand their varied forms can jump to the
:ref:`users-guide-4`. The :ref:`software-guide-4` provides information on
the software architecture, installation and configuration, and operational
considerations for those wishing to run a regional ShakeMap system.

To cite this manual:

Worden, C.B., E. M. Thompson, M. Hearne, and D.J. Wald (2020). ShakeMap
Manual Online: technical manual, user’s guide, and software guide,
U. S. Geological Survey. https://ghsc.code-pages.usgs.gov/esi/shakemap/.
DOI: https://doi.org/10.5066/F7D21VPQ.

.. toctree::
   :hidden:
   :numbered: 1
   :caption: Contents
   :maxdepth: 1

   Technical Guide <manual4_0/sm4_technical_guide>
   Users Guide <manual4_0/sm4_users_guide>
   Software and Implementation Guide <manual4_0/sm4_software_guide>
   Acknowledgments <manual4_0/sm4_acknowledgments>
   References and Bibliography <manual4_0/sm4_references>
   Glossary <manual4_0/sm4_glossary>


.. Indices and tables
.. ==================

.. * :ref:`genindex`

.. * :ref:`modindex`
.. * :ref:`search`
