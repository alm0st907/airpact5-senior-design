# Container with bluesky and all of it's dependencies.
#
# Example of how to use in dev environment, assuming you've built the
# image with tag 'bluesky':
#
#   docker run --rm -i \
#      -v /path/to/bluesky/repo/:/bluesky/ \
#      -e PYTHONPATH=/bluesky/ \
#      -e PATH=/bluesky/bin/:$PATH \
#      -w /bluesky/ \
#      bluesky ./bin/bsp ...
#
# And an example of how to use already installed bsp
#
#  docker run --rm -i bluesky bsp ...


FROM ubuntu:16.04
MAINTAINER Joel Dubowy


## Install Dependencies

# Install base dependencies
RUN apt-get update \
    && apt-get install -y \
        g++ \
        gcc \
        make \
        dialog \
        less \
        python3 \
        python3-dev \
        python3-pip

# upgrade distribute
RUN pip3 install --upgrade \
        distribute

# install png and freetype libs for matplotlib, which is needed
# by bluesky kml, as well as netcdf and proj libs
RUN apt-get install -y \
        libpng-dev \
        libfreetype6-dev \
        libnetcdf-dev \
        libproj-dev

# Install numpy (which must be installed first); gdal, it's python bindings,
# and it's utilities; and xml libs
RUN apt-get install -y \
        python3-numpy \
    && apt-get install -y \
        libgdal-dev \
        nco \
    && apt-get install -y \
        python3-gdal \
    && apt-get install -y \
        libxml2-dev \
        libxslt1-dev \
    && apt-get install -y \
        gdal-bin # install gdal-bin for gdalwarp and gdal_translate

# TODO: install libopenmpi1.10 and libmpich12 instead of the dev versions
RUN apt-get update \
    && apt-get install -y \
        libopenmpi-dev \
        libmpich-dev \
    && apt-get install -y \
        openmpi-bin

RUN pip3 install --upgrade pip

# blueskykml and consume are relatively static these days; so, install them
# here in order to avoid reinstalling them and their large dependencies
# (Pillow==2.8.1, 9.0MB, and matplotlib==1.4.3, 50.4MB, for blueskykml;
# pandas, etc. for consume) everytime the the bluesky image is built
# NOTE: these RUN commands will need to be updated if 'blueskykml'
#   and/or consume are ever updated in setup.py
RUN pip3 install \
    --extra-index https://pypi.airfire.org/simple blueskykml==2.3.0
RUN pip3 install \
    --extra-index https://pypi.airfire.org/simple apps-consume4==4.1.*

# Same thing for Fiona (which is 39.7MB)
# NOTE: asame as above - update this command if we upgrade to a newer version
#   in setup.py
RUN pip3 install Fiona==1.7.2

# Having vim is handy
RUN apt-get install -y \
        vim

# Install bluesky utils for merging emissions, etc.
RUN pip3 install \
    --extra-index https://pypi.airfire.org/simple blueskyutils>=0.2.0

# Install binary dependencies - for localmet, plumerise,
# dipersion, and visualization
COPY bin/feps_plumerise /usr/local/bin/feps_plumerise
COPY bin/feps_weather /usr/local/bin/feps_weather
COPY bin/hycm_std /usr/local/bin/hycm_std
COPY bin/hycs_std /usr/local/bin/hycs_std
COPY bin/hysplit2netcdf /usr/local/bin/hysplit2netcdf
COPY bin/profile /usr/local/bin/profile
COPY bin/vsmkgs /usr/local/bin/vsmkgs
COPY bin/vsmoke /usr/local/bin/vsmoke

# Install python dependencies
RUN mkdir /tmp/bluesky/
WORKDIR /tmp/bluesky/
COPY requirements.txt /tmp/bluesky/requirements.txt
COPY requirements-test.txt /tmp/bluesky/requirements-test.txt
RUN pip install --no-binary gdal -r requirements.txt

# Install bluesky package
COPY bluesky/ /tmp/bluesky/bluesky/
COPY bin/ /tmp/bluesky/bin/
COPY setup.py /tmp/bluesky/setup.py
RUN python3 setup.py install

# default command is to display bsp help string
CMD ["bsp", "-h"]
