class DetectionMethod:
    """検出手法に関する定数定義"""
    
    # 内部識別子
    NO_IMPORT = 'no-import'
    TKS = 'tks'
    CCFSW = 'ccfsw'  # Legacy (raw output with imports)

    # UI表示用ラベル
    LABELS = {
        NO_IMPORT: 'Normal',  # "Normal" means No-Import in UI
        TKS: 'TKS',
        CCFSW: 'Legacy (Raw)'
    }

    # ファイルプレフィックスとのマッピング
    # prefix (without underscore) -> method
    PREFIX_MAP = {
        'import': NO_IMPORT,
        'tks': TKS,
        '': CCFSW
    }

    @classmethod
    def get_options(cls):
        """UIコンポーネント用のオプションリストを生成"""
        # UIには Normal (No-Import) と TKS のみを表示するのが基本方針
        return [
            {'label': cls.LABELS[cls.NO_IMPORT], 'value': cls.NO_IMPORT},
            {'label': cls.LABELS[cls.TKS], 'value': cls.TKS}
        ]

    @classmethod
    def from_prefix(cls, prefix):
        """ファイルプレフィックスからメソッドを特定"""
        if prefix is None:
            prefix = ''
        # 末尾のアンダースコアを除去して小文字化
        clean_prefix = prefix.lower().rstrip('_')
        return cls.PREFIX_MAP.get(clean_prefix, cls.CCFSW)
