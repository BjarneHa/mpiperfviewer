import argparse
import re
import sys
from pathlib import Path

from matplotlib.figure import Figure

from create_views import MatrixGroupBy
from filtering.filters import FilterState
from parser import WorldData
from plotting.plots import (
    CountMatrixPlot,
    Counts2DBarPlot,
    PlotBase,
    SizeBar3DPlot,
    SizeMatrixPlot,
    SizePixelPlot,
    TagsBar3DPlot,
    TagsPixelPlot,
)

RANK_PLOTS = {
    "size_3d": SizeBar3DPlot,
    "size_px": SizePixelPlot,
    "tags_3d": TagsBar3DPlot,
    "tags_px": TagsPixelPlot,
    "counts": Counts2DBarPlot,
}
MATRIX_PLOTS = {"total_matrix": SizeMatrixPlot, "msgs_matrix": CountMatrixPlot}

GROUPINGS = {
    "rank": MatrixGroupBy.RANK,
    "numa": MatrixGroupBy.NUMA,
    "socket": MatrixGroupBy.SOCKET,
    "node": MatrixGroupBy.NODE,
}


def create_parser():
    matrix_plots_list = ", ".join([k + ".GROUP" for k in MATRIX_PLOTS.keys()])
    rank_plots_list = ", ".join([k + ".RANK" for k in RANK_PLOTS.keys()])
    parser = argparse.ArgumentParser(
        prog="mpiperfcli",
        description="Generate plots from MPI performance counter data.",
    )
    _ = parser.add_argument("directory", help="The directory of the benchmark data.")
    _ = parser.add_argument(
        "component", nargs="?", help="The component from which to process data."
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
        help="The default format for all plots where a filename was not specified.",
    )
    _ = parser.add_argument(
        "-d",
        "--dpi",
        default=300,
        type=float,
        help="The resolution in dots per inch.",
    )
    _ = parser.add_argument(
        "-t",
        "--transparent",
        action="store_true",
        help="Use a transparent background for all plots",
    )
    _ = parser.add_argument(
        "-p",
        "--plot",
        help="Export the specified plot. You can specify the filename using the format PLOTTYPE=FILENAME."
        + f" The available plot types are {matrix_plots_list} and {rank_plots_list}."
        + " For rank-specific plots, RANK needs to be specified."
        + f" For matrix plots, a grouping (one of {'/'.join(GROUPINGS.keys())}) needs to be specified.",
        action="append",
    )
    return parser


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
    tasks = list[tuple[str, PlotBase]]()
    for plot in parser_data.plot:
        match = re.match(r"(\w+)\.(\w+)(=(.+))?", plot)
        if match is None:
            print(
                f'Failed to parse plot argument "{plot}". Exiting...', file=sys.stderr
            )
            return
        plot, param, _, filename = match.groups()
        if filename is None:
            filename = plot + "." + parser_data.default_format
        matrix_class = MATRIX_PLOTS.get(plot)
        if matrix_class is not None:
            grouping = GROUPINGS.get(param.lower())
            if grouping is None:
                print(
                    f'Grouping "{grouping}" is not one of {"/".join(GROUPINGS.keys())}. Exiting...',
                    file=sys.stderr,
                )
                return

            tasks.append(
                (
                    filename,
                    matrix_class(Figure(), world_data.meta, component_data, grouping),
                )
            )
        else:
            rank_class = RANK_PLOTS.get(plot)
            if rank_class is None:
                print("Plot type does not exist. Exiting...", file=sys.stderr)
                return
            try:
                rank = int(param)
                if rank < 0 or rank > world_data.meta.num_processes:
                    raise ValueError("Rank out-of-range.")
            except ValueError:
                print(
                    f"A valid rank needs to be specified for plot type {plot}. Exiting...",
                    file=sys.stderr,
                )
                return
            tasks.append(
                (filename, rank_class(Figure(), world_data.meta, component_data, rank))
            )
    output_directory = (
        parser_data.output_directory
        if parser_data.output_directory is not None
        else Path(".")
    )
    for filename, task in tasks:
        complete_fname = output_directory / filename
        task.init_plot(FilterState())  # TODO find adequate format for filters
        task.fig.savefig(
            complete_fname,
            transparent=parser_data.transparent,
            dpi=parser_data.dpi,
        )


if __name__ == "__main__":
    main()
