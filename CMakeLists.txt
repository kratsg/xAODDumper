################################################################################
# Package: xAODDumper
################################################################################

# Declare the package name:
atlas_subdir( xAODDumper )

# Declare the package's dependencies:
atlas_depends_on_subdirs( PUBLIC
                          Control/AthContainers
                          Control/AthToolSupport/AsgTools
                          Control/xAODRootAccess
                          Event/xAOD/xAODBase
)

# Find the needed external(s):
find_package( ROOT COMPONENTS Core RIO Hist Tree )

# Install files from the package:
atlas_install_scripts( scripts/*.py )
