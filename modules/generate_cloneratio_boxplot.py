import sys
from pathlib import Path
import json

import matplotlib.pyplot as plt

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.calcurate_clone_ratio

if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
    results = {}
    for project in dataset:
        result = modules.calcurate_clone_ratio.analyze_repo(project)
        for language in result:
            if language not in results:
                results[language] = {
                    "within-testing_clone_ratio": [],
                    "within-production_clone_ratio": [],
                    "across-testing_clone_ratio": [],
                    "across-production_clone_ratio": []
                }
            for mode in result[language]:
                results[language][mode].append(result[language][mode])

    # 全言語全モードの箱ひげ図を横に並べて描画
    modes = ["within-testing_clone_ratio", "within-production_clone_ratio", "across-testing_clone_ratio", "across-production_clone_ratio"]
    languages = list(results.keys())

    fig, axes = plt.subplots(1, len(modes), figsize=(5 * len(modes), 6), sharey=True)

    if len(modes) == 1:
        axes = [axes]

    for idx, mode in enumerate(modes):
        data = []
        labels = []
        for language in languages:
            data.append(results[language][mode])
            labels.append(language)
        axes[idx].boxplot(data, labels=labels, showmeans=True)
        axes[idx].set_title(mode, fontsize=14)
        axes[idx].set_xlabel("言語", fontsize=12)
        if idx == 0:
            axes[idx].set_ylabel("クローン率", fontsize=12)
        axes[idx].tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.suptitle("全言語・全モードのクローン率 箱ひげ図", fontsize=16, y=1.03)
    plt.subplots_adjust(top=0.88)
    
    # PNG形式で保存
    output_path = project_root / "dest/cloneratio_boxplot.png"
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"箱ひげ図を保存しました: {output_path}")
    plt.show()