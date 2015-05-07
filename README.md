# xAODDumper - A RootCore Package

## Installing
This will work on (most) xAODs in (most) a given AnalysisBase release. To install,

```bash
git clone https://github.com/kratsg/xAODDumper.git
rc find_packages
rc compile
dumpSG.py <input file> *kwargs
```

It has been tested on Rel19 xAODs, Rel20 xAODs, DxAODs, mc14, and mc15 datasets. That is literally amazing!

### Functionality Included
 - `dumpSG.py` is a python script (a ROOT macro of sorts) used to inspect information about a ROOT file. It should be self-documented via `dumpSG.py --help`.

#### Example Usage

* Quick start. Outputs all types and containers in the file in a pretty-print format. Output file is 'info.dump'.
  ```
  dumpSG.py input.root
  ```

* Change the output format to json for more detailed reporting.
  ```
  dumpSG.py input.root -f json
  ```

* Use `ROOT::TChain` to add multiple input xAOD ROOT files for analysis. Note that an implicit assumption is all the ROOT files correspond to the same AthAnalysisBase release and have the same set of branches and leaves. Unexpected behavior can occur if they do not.
  ```
  dumpSG.py mc14_13TeV.110401.PowhegPythia_P2012_ttbar_nonallhad.merge.DAOD_SUSY4.e2928_s1982_s2008_r5787_r5853_*/*.root
  ```

* Print out more verbose information about the attributes and properties for all containers
  ```
  dumpSG.py input.root --prop --attr
  ```

* Filter the xAOD types being used, such as allowing only `xAOD::JetContainer` or `xAOD::JetEtRoIInfo`
  ```
  dumpSG.py input.root --type="xAOD::Jet*"
  ```

* Filter the xAOD containers being used, such as allowing only `AntiKt10` algorithms
  ```
  dumpSG.py input.root --container="*AntiKt10*"
  ```

* Create a directory of reports across the containers
  ```
  dumpSG.py input.root --report
  ```

* and sometimes, you might be running on X11 or a similar agent so you want to run this in batch mode since we use `ROOT::TTree::Draw` to build our plots
  ```
  dumpSG.py input.root --report -b
  ```

* and sometimes you want to make multiple reports for multiple datasets so you configure the output directory
  ```
  dumpSG.py input.root -d input --report -b
  ```

* and sometimes you prefer to have individual PDFs instead merging all the information plotted for a given container
  ```
  dumpSG.py input.root -d report --report --merge-report -b
  ```

* if a job does not run correctly, we can increase the verbosity level with the python execution or root execution
   ```
   dumpSG.py input.root -v
   dumpSG.py input.root -vv
   dumpSG.py input.root -vvvvvv
   ```

   or

   ```
   dumpSG.py input.root --debug-root
   ```

#### Understanding physical sizes of the containers

```
dumpSG.py input.root --format json --size --attr -b
```

will produce two sets of pie charts. One pie chart represents the physical space on the disk and the other represents the amount of space in memory (RAM)

<img src="https://github.com/kratsg/xAODDumper/raw/master/img/sizes_ondisk.png?raw=true" alt="On-Disk Sizes" width="325" />
<img src="https://github.com/kratsg/xAODDumper/raw/master/img/sizes_inmemory.png?raw=true" alt="In-Memory Sizes" width="325" />

### [dumpSG.py](scripts/dumpSG.py)
```
usage: dumpSG.py filename [filename] [options]

Process xAOD File and Dump Information.

positional arguments:
  input_filename        input root file(s) to read

optional arguments:
  -h, --help            show this help message and exit
  --tree TREE_NAME      Specify the tree that contains the StoreGate
                        structure. Default: CollectionTree
  -o OUTPUT_FILENAME, --output OUTPUT_FILENAME
                        Output file to store dumped information. Default:
                        info.dump
  -d OUTPUT_DIRECTORY, --output_directory OUTPUT_DIRECTORY
                        Output directory to store the report generated.
                        Default: report
  -t CONTAINER_TYPE_REGEX, --type CONTAINER_TYPE_REGEX
                        Regex specification for the xAOD container type. For
                        example, --type="xAOD::Jet*" will match
                        `xAOD::JetContainer` while --type="xAOD::*Jet*" will
                        match `xAOD::TauJetContainer`. This uses Unix filename
                        matching. Default: *
  -c CONTAINER_NAME_REGEX, --container CONTAINER_NAME_REGEX
                        Regex specification for the xAOD container name. For
                        example, --container="AntiKt10LCTopo*" will match
                        `AntiKt10LCTopoJets`. This uses Unix filename
                        matching. Default: *
  -f {json,pickle,pretty}, --format {json,pickle,pretty}
                        Specify the output format. Default: pretty
  -v, --verbose         Enable verbose output of various levels. Use --debug-
                        root to enable ROOT debugging. Default: no verbosity
  --debug-root          Enable ROOT debugging/output. Default: disabled
  -b, --batch           Enable batch mode for ROOT. Default: disabled
  --has_aux             Enable to only include containers which have an
                        auxillary container. By default, it includes all
                        containers it can find. Default: disabled
  --prop                Enable to print properties of container. By default,
                        it only prints the xAOD::ContainerType and containers
                        for that given type. This is like an increased
                        verbosity option for container properties. Default:
                        disabled
  --attr                Enable to print attributes of container. By default,
                        it only prints the xAOD::ContainerType and containers
                        for that given type. This is like an increased
                        verbosity option for container attributes. Default:
                        disabled
  --report              Enable to also create a directory containing plots and
                        generate additional reporting information/statistics.
                        By default, this is turned off as it can be
                        potentially slow. The output directory containing the
                        plots will be named `xAODDumper_Report`. Default:
                        disabled
  --merge-report        Enable to merge the generated report by container. By
                        default, this is turned off. Default: disabled
  --size                Enable to build a pie chart of the size distributions
                        in memory and on-disk. By default, this is turned off.
                        Default: disabled
  --noEntries NO_ENTRIES
                        If a plot generated by a report has no entries, color
                        it with this ROOT color value. Default: kRed
  --noRMS NO_RMS        If a plot generated by a report has RMS = 0.0 (mean !=
                        0.0), color it with this ROOT color value. Default:
                        kYellow
  --noMean NO_MEAN      If a plot generated by a report has mean = 0.0, color
                        it with this ROOT color value. Default: kOrange
  --filterProps PROPERTY_NAME_REGEX
                        (INACTIVE) Regex specification for xAOD property
                        names. Only used if --prop enabled.
  --filterAttrs ATTRIBUTE_NAME_REGEX
                        (INACTIVE) Regex specification for xAOD attribute
                        names. Only used if --attr enabled.
  -i, --interactive     (INACTIVE) Flip on/off interactive mode allowing you
                        to navigate through the container types and
                        properties.
```

### Known Bugs
- HLT Jets and other objects that are typed `AuxByteStreamContainer` are not easily introspected

### Authors
- [Giordon Stark](https://github.com/kratsg)

### Acknowledgements
- Thanks to [David Miller](http://fizisist.web.cern.ch/fizisist/Welcome.html) for the comments, critiques, and extensive testing. And basically being a bad-ass.
