#!/usr/bin/env python3

import argparse
import re
import sys
from itertools import chain
from pathlib import Path

from matplotlib.figure import Figure

from mpiperfcli.filters import (
    FilterState,
    FilterType,
    InvertedFilter,
    MultiRangeFilter,
    RangeFilter,
)
from mpiperfcli.parser import ComponentData, WorldData, WorldMeta
from mpiperfcli.plots import (
    CountMatrixPlot,
    Counts2DBarPlot,
    MatrixGroupBy,
    PlotBase,
    SizeBar3DPlot,
    SizeMatrixPlot,
    SizePixelPlot,
    TagsBar3DPlot,
    TagsPixelPlot,
)

RANK_PLOTS = {
    p.cli_name(): p
    for p in [
        SizeBar3DPlot,
        SizePixelPlot,
        TagsBar3DPlot,
        TagsPixelPlot,
        Counts2DBarPlot,
    ]
}
MATRIX_PLOTS = {
    p.cli_name(): p
    for p in [
        SizeMatrixPlot,
        CountMatrixPlot,
    ]
}

GROUPINGS = [g.name.lower() for g in MatrixGroupBy]


def create_plot_from_plot_and_param(
    plot: str,
    param: str,
    fig: Figure,
    world_meta: WorldMeta,
    component_data: ComponentData,
):
    matrix_class = MATRIX_PLOTS.get(plot)
    if matrix_class is not None:
        try:
            grouping = MatrixGroupBy[param.upper()]
        except KeyError:
            raise Exception(
                f'Grouping "{param}" is not one of {"/".join(GROUPINGS)}. Exiting...'
            )

        return matrix_class(fig, world_meta, component_data, grouping)
    else:
        rank_class = RANK_PLOTS.get(plot)
        if rank_class is None:
            raise Exception("Plot type does not exist. Exiting...")
        try:
            rank = int(param)
            if rank < 0 or rank > world_meta.num_processes:
                raise ValueError("Rank out-of-range.")
            return rank_class(fig, world_meta, component_data, rank)
        except ValueError:
            raise Exception(
                f"A valid rank needs to be specified for plot type {plot}. Exiting..."
            )


def create_parser():
    matrix_plots_list = ", ".join([k + ".GROUP" for k in MATRIX_PLOTS.keys()])
    rank_plots_list = ", ".join([k + ".RANK" for k in RANK_PLOTS.keys()])
    parser = argparse.ArgumentParser(
        prog="mpiperfcli",
        description="Generate plots from MPI performance counter data.",
    )
    _ = parser.add_argument("directory", help="The directory of the benchmark data.")
    _ = parser.add_argument(
        "component",
        nargs="?",
        help="The component from which to process data."
        + " If none is given, the program will terminate except if data is only available for one component.",
    )
    _ = parser.add_argument(
        "-o",
        "--output-directory",
        help="The directory in which plots will be placed.",
        type=Path,
    )
    _ = parser.add_argument(
        "-f",
        "--default-format",
        default="pdf",
        help="The default format for all plots where a filename was not specified (default: pdf).",
    )
    _ = parser.add_argument(
        "-d",
        "--dpi",
        default=300,
        type=float,
        help="The resolution in dots per inch (default: 300).",
    )
    _ = parser.add_argument(
        "-t",
        "--transparent",
        action="store_true",
        help="Use a transparent background for all plots (default: off)",
    )
    _ = parser.add_argument(
        "-p",
        "--plot",
        help="Export the specified plot. You can specify the filename using the format PLOTTYPE=FILENAME."
        + f" The available plot types are {matrix_plots_list} and {rank_plots_list}."
        + ' For rank-specific plots, RANK needs to be specified. RANK may be "*" to create plot for all ranks.'
        + f" For matrix plots, a grouping (one of {'/'.join(GROUPINGS)}) needs to be specified.",
        action="append",
    )
    _ = parser.add_argument(
        "--wildcard-rank-min-field-width",
        help="Specify the minimum field width for the rank number in file names if plots are created with a wildcard."
        + " By default, the rank will be padded with just enough zeroes such that all file names are in lexicographical order."
        + " Specify a width of 0 for no padding.",
        type=int,
    )
    _ = parser.add_argument(
        "-x",
        "--filter",
        help="Set the filters for a certain plot type. Syntax: PLOTTYPE=FILTER=FILTER=..."
        + " Here's a list of the available filters for all plot types:\n"
        + ", ".join(
            [
                f"{name}: "
                + (
                    "none"
                    if len(plot_class.filter_types()) == 0
                    else "{"
                    + ", ".join(
                        [f"{ft.name.lower()}" for ft in plot_class.filter_types()]
                    )
                    + "}"
                )
                for name, plot_class in chain(MATRIX_PLOTS.items(), RANK_PLOTS.items())
            ]
        )
        + '. A FILTER is specified with a name and a comma-separated list of ranges and exact values. E.g. "tags:[-20;10],4,[12;14]". Note that for the count filter, only one range may be specified.',
        action="append",
    )
    return parser

def parse_filter(s: str):
    filter_text = s[1:] if s.startswith("!") else s
    filter = MultiRangeFilter.from_str(filter_text)
    if s.startswith("!"):
        return InvertedFilter(filter)
    else:
        return filter

def main():
    parser = create_parser()
    parser_data = parser.parse_args()
    world_data = WorldData(Path(parser_data.directory))
    component = parser_data.component
    if parser_data.component is None:
        print(f"Components found in data: {', '.join(world_data.components.keys())}.")
        if len(world_data.components) > 1:
            parser.print_help()
            print(
                "Data has more than one component, yet none was specified. Exiting...",
                file=sys.stderr,
            )
            return
        component = list(world_data.components.keys())[0]
    component_data = world_data.components.get(component)
    if component_data is None:
        print("Component does not exist in data. Exiting...", file=sys.stderr)
        return
    if parser_data.plot is None or len(parser_data.plot) == 0:
        print("No plots specified. Exiting...")
        return

    filters = dict[type[PlotBase], FilterState]()
    if parser_data.filter is None:
        parser_data.filter = list[str]()

    for filter in parser_data.filter:
        plot_name, *plot_filters = filter.split("=")
        plot_class = MATRIX_PLOTS.get(plot_name, RANK_PLOTS.get(plot_name))
        if plot_class is None:
            print(
                f'Plot type "{plot_name}" does not exist. Exiting...', file=sys.stderr
            )
            return
        filters[plot_class] = FilterState()

        for pf in plot_filters:
            filter_name, filter_text = pf.split(":", 1)
            try:
                filter_type = FilterType[filter_name.upper()]
                if filter_type not in plot_class.filter_types():
                    raise KeyError()
            except KeyError:
                print(
                    f'Filter "{filter_name}" is not available for plot type "{plot_name}". Exiting...',
                    file=sys.stderr,
                )
                return
            try:
                match filter_type:
                    case FilterType.COUNT:
                        range_filter = RangeFilter.from_str(filter_text)
                        if range_filter is None:
                            raise ValueError(
                                f'Failed to parse "{filter_text}". A single range in the format [min;max] was expected.'
                            )
                        filters[plot_class].count = range_filter
                    case FilterType.SIZE:
                        filters[plot_class].size = parse_filter(filter_text)
                    case FilterType.TAGS:
                        filters[plot_class].tags = parse_filter(filter_text)
            except ValueError as e:
                print(
                    f'Error parsing "{filter_name}" for plot type "{plot_name}": {e}. Exiting...',
                    file=sys.stderr,
                )
                return

    plot_bases = list[tuple[str, PlotBase]]()
    for plot in parser_data.plot:
        match = re.match(r"(\w+)\.(\*|\w+)(?:=(.+))?", plot)
        if match is None:
            print(
                f'Failed to parse plot argument "{plot}". Exiting...', file=sys.stderr
            )
            return
        plot, param, filename = match.groups()
        if filename is None:
            filename = f"{plot}_{param}.{parser_data.default_format}"
        if param == "*":
            if RANK_PLOTS.get(plot) is None:
                print(
                    f'"{plot}" plot does not allow a wildcard as a parameter, or does not exist. Exiting...',
                    file=sys.stderr,
                )
                return
            name, ext = filename.rsplit(".", 1)
            if parser_data.wildcard_rank_min_field_width is None:
                rank_width = len(str(world_data.meta.num_processes))
            elif parser_data.wildcard_rank_min_field_width >= 0:
                rank_width = parser_data.wildcard_rank_min_field_width
            else:
                print(
                    "Value for --wildcard-rank-min-field-width must be positive. Exiting...",
                    file=sys.stderr,
                )
                return
            for rank in range(world_data.meta.num_processes):
                plot_object = create_plot_from_plot_and_param(
                    plot, str(rank), Figure(), world_data.meta, component_data
                )
                plot_bases.append(
                    (name + f"_{rank:0{rank_width}d}." + ext, plot_object)
                )
        else:
            plot_object = create_plot_from_plot_and_param(
                plot, param, Figure(), world_data.meta, component_data
            )
            plot_bases.append((filename, plot_object))
    output_directory = (
        parser_data.output_directory
        if parser_data.output_directory is not None
        else Path(".")
    )
    for filename, plot_base in plot_bases:
        complete_fname = output_directory / filename
        plot_base.draw_plot(filters.get(type(plot_base), FilterState()))
        plot_base.fig.savefig(
            complete_fname,
            transparent=parser_data.transparent,
            dpi=parser_data.dpi,
        )


if __name__ == "__main__":
    main()
