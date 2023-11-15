#!/usr/bin/env bash

# constants
DEFAULT_PYVER=3.9

usage()
{
  echo "Usage: install.sh [ -u  Update]
                  [ -t  Run tests ]
                  [ -n  Don't run tests]
            "
  exit 2
}

unamestr=`uname`
if [ "$unamestr" == 'Linux' ]; then
    prof=~/.bashrc
    mini_conda_url=https://repo.continuum.io/miniconda/Miniconda3-latest-Linux-x86_64.sh
    matplotlibdir=~/.config/matplotlib
elif [ "$unamestr" == 'FreeBSD' ] || [ "$unamestr" == 'Darwin' ]; then
    prof=~/.bash_profile
    mini_conda_url=https://repo.continuum.io/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
    matplotlibdir=~/.matplotlib
else
    echo "Unsupported environment. Exiting."
    exit
fi

# execute the user's profile
source $prof


# Parse the command line arguments passed in by the user
PYVER=$DEFAULT_PYVER
run_tests=false
input_yaml_file=source_environment.yml
# Default is to use conda to install since mamba fails on some systems
install_pgm=conda
while getopts ":utp:n" options; do
    case "${options}" in                    # 
    p)
        PYVER=$OPTARG
        ;;
    t)
        run_tests=true
        ;;
    n)
        run_tests=false
        ;;
    *)                            # If unknown (any other) option:
      usage                       # Exit abnormally.
      ;;
    esac
done

echo "YAML file to use as input: ${input_yaml_file}"
echo "Using python version ${PYVER}"

# Name of virtual environment, pull from yml file
VENV=`grep "name:" source_environment.yml  | cut -f2 -d ":" | sed 's/ //g'`
echo "#####Environment to create: '${VENV}'"

# Where is conda installed?
CONDA_LOC=`which conda`
echo "######Location of conda install: ${CONDA_LOC}"

# Are we in an environment
CURRENT_ENV=`conda info --envs | grep "*"`
echo "Current conda environment: ${CURRENT_ENV}"

# create a matplotlibrc file with the non-interactive backend "Agg" in it.
if [ ! -d "$matplotlibdir" ]; then
    mkdir -p $matplotlibdir
    # if mkdir fails, bow out gracefully
    if [ $? -ne 0 ];then
        echo "Failed to create matplotlib configuration file. Exiting."
        exit 1
    fi
fi

matplotlibrc=$matplotlibdir/matplotlibrc
if [ ! -e "$matplotlibrc" ]; then
    echo "backend : Agg" > "$matplotlibrc"
    echo "NOTE: A non-interactive matplotlib backend (Agg) has been set for this user."
elif grep -Fxq "backend : Agg" $matplotlibrc ; then
    :
elif [ ! grep -Fxq "backend" $matplotlibrc ]; then
    echo "backend : Agg" >> $matplotlibrc
    echo "NOTE: A non-interactive matplotlib backend (Agg) has been set for this user."
else
    sed -i '' 's/backend.*/backend : Agg/' $matplotlibrc
    echo "###############"
    echo "NOTE: $matplotlibrc has been changed to set 'backend : Agg'"
    echo "###############"
fi

# Is conda installed?
conda --version
if [ $? -ne 0 ]; then
    echo "No conda detected, installing miniconda..."

    command -v curl >/dev/null 2>&1 || { echo >&2 "Script requires curl but it's not installed. Aborting."; exit 1; }

    curl -L $mini_conda_url -o miniconda.sh;

    # if curl fails, bow out gracefully
    if [ $? -ne 0 ];then
        echo "Failed to download miniconda installer shell script. Exiting."
        exit 1
    fi
    
    echo "Install directory: $HOME/miniconda"

    bash miniconda.sh -f -b -p $HOME/miniconda

    # if miniconda.sh fails, bow out gracefully
    if [ $? -ne 0 ];then
        echo "Failed to run miniconda installer shell script. Exiting."
        exit 1
    fi
    
    . $HOME/miniconda/etc/profile.d/conda.sh

    # remove the shell script
    rm miniconda.sh
else
    echo "conda detected, installing $VENV environment..."
fi


# Update the conda tool
CVNUM=`conda -V | cut -f2 -d' '`
LATEST=`conda search conda | tail -1 | tr -s ' ' | cut -f2 -d" "`
echo "${CVNUM}"
echo "${LATEST}"
if [ ${LATEST} != ${CVNUM} ]; then
    echo "##################Updating conda tool..."
    CVERSION=`conda -V`
    echo "Current conda version: ${CVERSION}"
    conda update -n base -c defaults conda -y
    CVERSION=`conda -V`
    echo "New conda version: ${CVERSION}"
    echo "##################Done updating conda tool..."
else
    echo "conda ${CVNUM} already matches latest version ${LATEST}. No update required."
fi

# Start in conda base environment
echo "Activate base virtual environment"
# The documentation for this command says:
# "writes the shell code to register the initialization code for the conda shell code."
# The ShakeMap developers will buy an ice cream for anyone who can explain the previous sentence.
# whatever it does, it is crucially important for being able to activate a conda environment
# inside a shell script.
eval "$(conda shell.bash hook)"                                                
conda activate base
if [ $? -ne 0 ]; then
    "Failed to activate conda base environment. Exiting."
    exit 1
fi

# Remove existing shakemap environment if it exists
conda remove -y -n $VENV --all
conda clean -y --all

# Install the virtual environment
echo "Creating new environment from environment file: ${input_yaml_file} with python version ${PYVER}"
# change python version in yaml file to match PYVER
sed 's/python='"${DEFAULT_PYVER}"'/python='"${PYVER}"'/' "${input_yaml_file}" > tmp.yml
${install_pgm} env create -f tmp.yml
rm tmp.yml 


# Bail out at this point if the conda create command fails.
# Clean up zip files we've downloaded
if [ $? -ne 0 ]; then
    echo "Failed to create conda environment.  Resolve any conflicts, then try again."
    exit 1
fi

# Activate the new environment
echo "Activating the $VENV virtual environment"
conda activate $VENV

# if conda activate fails, bow out gracefully
if [ $? -ne 0 ];then
    echo "Failed to activate ${VENV} conda environment. Exiting."
    exit 1
fi

# The presence of a __pycache__ folder in bin/ can cause the pip
# install to fail... just to be safe, we'll delete it here.
if [ -d bin/__pycache__ ]; then
    rm -rf bin/__pycache__
fi

if $developer; then
    echo "############# Installing shakemap with developer tools ##############"
    if ! pip install -e '.[dev,test,doc]' ; then
        echo "Installation of shakemap failed."
        exit 1
    fi
else
    echo "############# Installing shakemap ##############"
    if ! pip install . ; then
        echo "Installation of shakemap failed."
        exit 1
    fi
fi

echo "Reminder: Run 'conda activate shakemap' to enable the ShakeMap environment."
