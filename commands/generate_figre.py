import sys
from pathlib import Path
import matplotlib.pyplot as plt
import json
import git
import numpy as np

project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

import modules.calculate_comodification_rate
import modules.calculate_clone_ratio


def create_clone_ratio_chart_for_project_language(project_data, language, output_dir=None):
    """
    単一プロジェクトの単一言語のクローン率と同時修正率を縦向きの棒グラフで可視化する
    
    Args:
        project_data: 単一プロジェクトのデータ
        language: 対象言語
        output_dir: 出力ディレクトリ（Noneの場合は表示のみ）
    """
    # 日本語フォントの設定
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
    project_name = project_data['name']
    clone_ratio = project_data['clone_ratio']
    comodification_rate = project_data['comodification_rate']
    
    # 指定された言語のデータを取得
    lang_clone_data = clone_ratio.get(language, {})
    lang_comod_data = comodification_rate.get(language, {})
    
    modes = ["within-testing", "within-production", "across-testing", "across-production"]
    mode_titles = {
        "within-testing": "Within Testing",
        "within-production": "Within Production", 
        "across-testing": "Across Testing",
        "across-production": "Across Production"
    }
    
    # データの準備
    clone_ratio_values = []
    comod_ratio_values = []
    
    for mode in modes:
        # クローン率の取得
        clone_ratio_value = lang_clone_data.get(f"{mode}_clone_ratio", 0)
        
        # 同時修正率の計算
        mode_comod_data = lang_comod_data.get(mode, {"count": 0, "comodification_count": 0})
        total_clones = mode_comod_data["count"]
        total_comodifications = mode_comod_data["comodification_count"]
        comod_ratio = total_comodifications / total_clones if total_clones > 0 else 0
        
        clone_ratio_values.append(clone_ratio_value)
        comod_ratio_values.append(comod_ratio)
    
    # データをnumpy配列に変換
    clone_ratio_values = np.array(clone_ratio_values)
    comod_ratio_values = np.array(comod_ratio_values)
    
    # 同時修正される部分のクローン率
    comodified_clone = clone_ratio_values * comod_ratio_values
    # 同時修正されない部分のクローン率
    non_comodified_clone = clone_ratio_values - comodified_clone
    
    # グラフの作成
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Y軸の位置
    y_pos = np.arange(len(modes))
    
    # 積み上げ棒グラフ（横向き）- 棒を細くするためheightを調整
    # オレンジを右端から開始するように順序を変更
    bar_height = 0.6  # 棒の太さを調整（デフォルトは0.8）
    bars1 = ax.barh(y_pos, comodified_clone, height=bar_height, color='orange', 
                    label='Comodified clone', alpha=0.8)
    bars2 = ax.barh(y_pos, non_comodified_clone, left=comodified_clone, height=bar_height,
                    color='lightblue', label='Non-comodified clone', alpha=0.8)
    
    # グラフの設定
    ax.set_yticks(y_pos)
    ax.set_yticklabels([mode_titles[mode] for mode in modes], fontsize=12)
    ax.set_xlabel('Clone Ratio', fontsize=14)
    ax.set_title(f'Clone Ratio with Co-modification Rate\n{project_name} - {language}', 
                 fontsize=16, fontweight='bold', pad=20)
    ax.grid(axis='x', alpha=0.3)
    
    # X軸の範囲設定
    ax.set_xlim(0, 1)
    
    # 値をバーの右に表示
    for i, (total, comod) in enumerate(zip(clone_ratio_values, comod_ratio_values)):
        if total > 0:
            ax.text(total + 0.02, i, 
                   f'{total:.3f}\n({comod:.1%})', 
                   ha='left', va='center', fontsize=10, fontweight='bold')
    
    plt.tight_layout()
    
    if output_dir:
        # プロジェクト名と言語名を安全なファイル名に変換
        safe_project_name = project_name.replace("/", "_").replace(".", "_")
        safe_language_name = language.replace("/", "_").replace(".", "_")
        output_path = Path(output_dir) / f"clone_ratio_{safe_project_name}_{safe_language_name}.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"グラフを保存しました: {output_path}")
        plt.close()  # メモリを節約するため明示的にクローズ
    else:
        plt.show()


def create_clone_ratio_chart_for_project(project_data, output_dir=None):
    """
    単一プロジェクトのクローン率と同時修正率を横向きの棒グラフで可視化する（従来の機能を保持）
    
    Args:
        project_data: 単一プロジェクトのデータ
        output_dir: 出力ディレクトリ（Noneの場合は表示のみ）
    """
    # 日本語フォントの設定
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
    project_name = project_data['name']
    clone_ratio = project_data['clone_ratio']
    comodification_rate = project_data['comodification_rate']
    
    # 言語ごとのデータを収集
    languages = list(clone_ratio.keys())
    clone_ratios = {
        "within-testing": [],
        "within-production": [],
        "across-testing": [],
        "across-production": []
    }
    comodification_ratios = {
        "within-testing": [],
        "within-production": [],
        "across-testing": [],
        "across-production": []
    }
    
    # 各言語とモードのデータを集計
    for language in languages:
        for mode in ["within-testing", "within-production", "across-testing", "across-production"]:
            # クローン率の取得
            lang_clone_data = clone_ratio.get(language, {})
            clone_ratio_value = lang_clone_data.get(f"{mode}_clone_ratio", 0)
            
            # 同時修正率の計算
            lang_comod_data = comodification_rate.get(language, {}).get(mode, {"count": 0, "comodification_count": 0})
            total_clones = lang_comod_data["count"]
            total_comodifications = lang_comod_data["comodification_count"]
            comod_ratio = total_comodifications / total_clones if total_clones > 0 else 0
            
            clone_ratios[mode].append(clone_ratio_value)
            comodification_ratios[mode].append(comod_ratio)
    
    # グラフの作成
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle(f'Clone Ratio with Co-modification Rate - {project_name}', fontsize=16, fontweight='bold')
    
    modes = ["within-testing", "within-production", "across-testing", "across-production"]
    mode_titles = {
        "within-testing": "Within Testing",
        "within-production": "Within Production", 
        "across-testing": "Across Testing",
        "across-production": "Across Production"
    }
    
    for idx, mode in enumerate(modes):
        ax = axes[idx // 2, idx % 2]
        
        # データの準備
        clone_ratio_values = np.array(clone_ratios[mode])
        comod_ratio_values = np.array(comodification_ratios[mode])
        
        # 同時修正される部分のクローン率
        comodified_clone = clone_ratio_values * comod_ratio_values
        # 同時修正されない部分のクローン率
        non_comodified_clone = clone_ratio_values - comodified_clone
        
        # 横向き棒グラフの作成
        y_pos = np.arange(len(languages))
        
        # 積み上げ棒グラフ
        bars1 = ax.barh(y_pos, non_comodified_clone, color='lightblue', 
                       label='Non-comodified clone', alpha=0.8)
        bars2 = ax.barh(y_pos, comodified_clone, left=non_comodified_clone,
                       color='orange', label='Comodified clone', alpha=0.8)
        
        # グラフの設定
        ax.set_yticks(y_pos)
        ax.set_yticklabels(languages, fontsize=10)
        ax.set_xlabel('Clone Ratio', fontsize=12)
        ax.set_title(mode_titles[mode], fontsize=14, fontweight='bold')
        ax.legend(loc='lower right', fontsize=10)
        ax.grid(axis='x', alpha=0.3)
        
        # X軸の範囲設定
        max_ratio = max(clone_ratio_values) if len(clone_ratio_values) > 0 and max(clone_ratio_values) > 0 else 1
        ax.set_xlim(0, max_ratio * 1.1)
        
        # 値をバーに表示
        for i, (total, comod) in enumerate(zip(clone_ratio_values, comod_ratio_values)):
            if total > 0:
                ax.text(total + max_ratio * 0.01, i, 
                       f'{total:.3f}\n({comod:.1%})', 
                       va='center', ha='left', fontsize=9)
    
    plt.tight_layout()
    
    if output_dir:
        # プロジェクト名を安全なファイル名に変換
        safe_project_name = project_name.replace("/", "_").replace(".", "_")
        output_path = Path(output_dir) / f"clone_ratio_{safe_project_name}_all_languages.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"プロジェクト全言語のグラフを保存しました: {output_path}")
        plt.close()  # メモリを節約するため明示的にクローズ
    else:
        plt.show()


def create_clone_ratio_with_comodification_chart(projects_data, output_dir=None):
    """
    すべてのプロジェクトのクローン率と同時修正率を横向きの棒グラフで可視化する（従来の機能）
    
    Args:
        projects_data: プロジェクトデータのリスト
        output_dir: 出力ディレクトリ（Noneの場合は表示のみ）
    """
    # 日本語フォントの設定
    plt.rcParams['font.family'] = 'DejaVu Sans'
    
    # プロジェクトごとのデータを収集
    project_names = []
    clone_ratios = {
        "within-testing": [],
        "within-production": [],
        "across-testing": [],
        "across-production": []
    }
    comodification_ratios = {
        "within-testing": [],
        "within-production": [],
        "across-testing": [],
        "across-production": []
    }
    
    for project_data in projects_data:
        project_name = project_data['name']
        clone_ratio = project_data['clone_ratio']
        comodification_rate = project_data['comodification_rate']
        
        project_names.append(project_name)
        
        # 各モードのデータを集計
        for mode in ["within-testing", "within-production", "across-testing", "across-production"]:
            # 全言語のクローン率の平均を計算
            total_clone_ratio = 0
            total_comod_ratio = 0
            language_count = 0
            
            for language, lang_data in clone_ratio.items():
                if f"{mode}_clone_ratio" in lang_data:
                    total_clone_ratio += lang_data[f"{mode}_clone_ratio"]
                    language_count += 1
            
            # 同時修正率の計算
            total_clones = 0
            total_comodifications = 0
            for language, lang_data in comodification_rate.items():
                if mode in lang_data:
                    total_clones += lang_data[mode]["count"]
                    total_comodifications += lang_data[mode]["comodification_count"]
            
            avg_clone_ratio = total_clone_ratio / language_count if language_count > 0 else 0
            comod_ratio = total_comodifications / total_clones if total_clones > 0 else 0
            
            clone_ratios[mode].append(avg_clone_ratio)
            comodification_ratios[mode].append(comod_ratio)
    
    # グラフの作成
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    fig.suptitle('Clone Ratio with Co-modification Rate by Mode', fontsize=16, fontweight='bold')
    
    modes = ["within-testing", "within-production", "across-testing", "across-production"]
    mode_titles = {
        "within-testing": "Within Testing",
        "within-production": "Within Production", 
        "across-testing": "Across Testing",
        "across-production": "Across Production"
    }
    
    for idx, mode in enumerate(modes):
        ax = axes[idx // 2, idx % 2]
        
        # データの準備
        clone_ratio_values = np.array(clone_ratios[mode])
        comod_ratio_values = np.array(comodification_ratios[mode])
        
        # 同時修正される部分のクローン率
        comodified_clone = clone_ratio_values * comod_ratio_values
        # 同時修正されない部分のクローン率
        non_comodified_clone = clone_ratio_values - comodified_clone
        
        # 横向き棒グラフの作成
        y_pos = np.arange(len(project_names))
        
        # 積み上げ棒グラフ
        bars1 = ax.barh(y_pos, non_comodified_clone, color='lightblue', 
                       label='Non-comodified clone', alpha=0.8)
        bars2 = ax.barh(y_pos, comodified_clone, left=non_comodified_clone,
                       color='orange', label='Comodified clone', alpha=0.8)
        
        # グラフの設定
        ax.set_yticks(y_pos)
        ax.set_yticklabels(project_names, fontsize=10)
        ax.set_xlabel('Clone Ratio', fontsize=12)
        ax.set_title(mode_titles[mode], fontsize=14, fontweight='bold')
        ax.legend(loc='lower right', fontsize=10)
        ax.grid(axis='x', alpha=0.3)
        ax.set_xlim(0, max(clone_ratio_values) * 1.1 if len(clone_ratio_values) > 0 else 1)
        
        # 値をバーに表示
        for i, (total, comod) in enumerate(zip(clone_ratio_values, comod_ratio_values)):
            if total > 0:
                ax.text(total + max(clone_ratio_values) * 0.01, i, 
                       f'{total:.3f}\n({comod:.1%})', 
                       va='center', ha='left', fontsize=9)
    
    plt.tight_layout()
    
    if output_dir:
        output_path = Path(output_dir) / "clone_ratio_with_comodification_all.png"
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"全プロジェクトのグラフを保存しました: {output_path}")
        plt.close()
    else:
        plt.show()


if __name__ == "__main__":
    dataset_file = project_root / "dataset/selected_projects.json"
    with open(dataset_file, "r") as f:
        dataset = json.load(f)
        
        # プロジェクトデータを収集
        projects_data = []
        
        for project in dataset:
            url = project["URL"]
            name = url.split("/")[-2] + "." + url.split("/")[-1]
            
            try:
                git_repo = git.Repo(project_root / "dest/projects" / name)
                head_commit = git_repo.head.commit
                
                # データを分析
                comodification_rate = modules.calculate_comodification_rate.analyze_repo(project)
                clone_ratio = modules.calculate_clone_ratio.analyze_repo(project)
                
                projects_data.append({
                    'name': name,
                    'url': url,
                    'clone_ratio': clone_ratio,
                    'comodification_rate': comodification_rate
                })
                
                print(f"分析完了: {name}")
                
            except Exception as e:
                print(f"エラー ({name}): {e}")
                continue
        
        # プロジェクトごと・言語ごとに個別のグラフを生成
        if projects_data:
            output_dir = project_root / "dest"
            total_charts = 0
            
            # 各プロジェクトごと・言語ごとに個別のグラフを作成
            for project_data in projects_data:
                project_name = project_data['name']
                clone_ratio = project_data['clone_ratio']
                languages = list(clone_ratio.keys())
                
                print(f"プロジェクト '{project_name}' のグラフを生成中...")
                
                # 言語ごとに個別のグラフを作成
                for language in languages:
                    print(f"  - {language} のグラフを生成中...")
                    create_clone_ratio_chart_for_project_language(
                        project_data, language, output_dir=output_dir
                    )
                    total_charts += 1
                
                # プロジェクトの全言語をまとめたグラフも作成
                print(f"  - {project_name} の全言語まとめグラフを生成中...")
                create_clone_ratio_chart_for_project(project_data, output_dir=output_dir)
                total_charts += 1
            
            # 全プロジェクトをまとめたグラフも作成
            print("全プロジェクトのまとめグラフを生成中...")
            create_clone_ratio_with_comodification_chart(projects_data, output_dir=output_dir)
            total_charts += 1
            
            print(f"合計 {total_charts} 個のグラフを生成しました。")
        else:
            print("分析可能なプロジェクトがありませんでした。")