import matplotlib.pyplot as plt
import os
import numpy as np
from argparse import ArgumentParser
from functools import partial
from scipy import stats
from collections import namedtuple, OrderedDict
from typing import Any, Dict, List, Optional

from adaptiveleak.utils.constants import POLICIES
from adaptiveleak.utils.file_utils import read_json_gz
from adaptiveleak.analysis.plot_utils import COLORS, to_label, geometric_mean, MARKER, MARKER_SIZE, LINE_WIDTH, PLOT_STYLE
from adaptiveleak.analysis.plot_utils import PLOT_SIZE, AXIS_FONT, LEGEND_FONT, TITLE_FONT
from adaptiveleak.analysis.plot_utils import extract_results, iterate_policy_folders



def plot(sim_results: Dict[str, Dict[float, float]], dataset_name: str, output_file: Optional[str]):

    with plt.style.context(PLOT_STYLE):
        fig, ax = plt.subplots(figsize=PLOT_SIZE)

        for name in POLICIES:
            if name not in sim_results:
                continue

            model_results = sim_results[name]
            targets = list(sorted(model_results.keys()))
            accuracy = [model_results[t]['test_accuracy'] * 100.0 for t in targets]

            ax.plot(targets, accuracy, marker=MARKER, linewidth=LINE_WIDTH, markersize=MARKER_SIZE, label=to_label(name), color=COLORS[name])

            print('{0} & {1:.2f}\\% ({2:.2f}\\%)'.format(name, geometric_mean(accuracy), np.max(accuracy)))

        ax.set_xlabel('Fraction of Measurements', fontsize=AXIS_FONT)
        ax.set_ylabel('Accuracy', fontsize=AXIS_FONT)
        ax.set_title('Attacker Accuracy on the {0} Dataset'.format(dataset_name.capitalize()), fontsize=TITLE_FONT)

        ax.legend(fontsize=LEGEND_FONT)

        if output_file is None:
            plt.show()
        else:
            plt.savefig(output_file, bbox_inches='tight')
        

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--dates', type=str, nargs='+', required=True)
    parser.add_argument('--dataset', type=str, required=True)
    parser.add_argument('--output-file', type=str)
    args = parser.parse_args()

    extract_fn = partial(extract_results, field='attack', aggregate_mode=None)
    policy_folders = iterate_policy_folders(args.dates, dataset=args.dataset)

    sim_results = {name: res for name, res in map(extract_fn, policy_folders)}
    plot(sim_results, output_file=args.output_file, dataset_name=args.dataset)
