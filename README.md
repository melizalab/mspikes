
## mspikes

**mspikes** is a general-purpose tool for processing time-varying data. It can
read and write files of various formats and perform a range of filtering and
detection operations. You can:

* filter acoustic recordings
* extract field potentials and spike waveforms from extracellular neural recordings
* export spike times and waveforms for spike sorting (using third-party programs) and import the results
* export spike times to generic formats
* add processing or I/O modules as plugins
* design your own mulithreaded processing pipelines using existing or plugin modules

Want to learn more? Visit the [wiki](https://github.com/dmeliza/mspikes/wiki).

## Quick install

**mspikes** 3.0 is under development, so you'll have to build it from source. Installing in a virtualenv is strongly encouraged.

````
git clone https://github.com/mspikes/mspikes.git
cd mspikes
python setup.py install
````


