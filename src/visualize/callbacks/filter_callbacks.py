"""フィルタリング関連のコールバック."""
import logging
import json

import dash
import pandas as pd
from dash import Input, Output, State, ALL, no_update, html

from ..data_loader import load_and_process_data
from ..components import generate_cross_service_filter_options
from modules.util import get_file_type

logger = logging.getLogger(__name__)

CODE_TYPE_COLORS = {
    "all": {
        "bg": "#f8f9fa",
        "border": "#d1d5da",
        "text": "#24292e",
        "active_bg": "#e1e4e8",
        "active_border": "#586069",
    },
    "logic": {
        "bg": "#f1f8ff",
        "border": "#c8e1ff",
        "text": "#0366d6",
        "active_bg": "#dbedff",
        "active_border": "#0366d6",
    },
    "data": {
        "bg": "#ffeef0",
        "border": "#f9d0c4",
        "text": "#d73a49",
        "active_bg": "#ffdce0",
        "active_border": "#d73a49",
    },
    "test": {
        "bg": "#e6ffed",
        "border": "#cdfeb8",
        "text": "#28a745",
        "active_bg": "#ccffd8",
        "active_border": "#28a745",
    },
    "config": {
        "bg": "#fafbfc",
        "border": "#e1e4e8",
        "text": "#6a737d",
        "active_bg": "#f6f8fa",
        "active_border": "#6a737d",
    },
    "mixed": {
        "bg": "#f3f0ff",
        "border": "#e0d8ff",
        "text": "#6f42c1",
        "active_bg": "#e5dbff",
        "active_border": "#6f42c1",
    },
}


def create_code_type_button(label, count, value, active_value):
    isActive = value == active_value
    colors = CODE_TYPE_COLORS.get(value, CODE_TYPE_COLORS["all"])

    style = {
        "padding": "4px 10px",
        "border": f'1px solid {colors["active_border"] if isActive else colors["border"]}',
        "borderRadius": "20px",
        "backgroundColor": colors["active_bg"] if isActive else colors["bg"],
        "color": colors["text"],
        "fontSize": "12px",
        "fontWeight": "600" if isActive else "normal",
        "cursor": "pointer",
        "boxShadow": (
            "0 1px 2px rgba(0,0,0,0.05)"
            if not isActive
            else "inset 0 1px 2px rgba(0,0,0,0.1)"
        ),
        "transition": "all 0.2s ease",
        "opacity": (
            "1.0" if isActive or count > 0 else "0.5"
        ),  # Fade if 0 counts but not active,
        "marginRight": "5px",  # Inline spacing
    }

    return html.Button(
        f"{label} ({count})",
        id={"type": "code-type-btn", "index": value},
        n_clicks=0,
        style=style,
    )




def register_filter_callbacks(app, app_data):
    """フィルタリング（コードタイプ・クロスサービス）関連のコールバックを登録する."""

    @app.callback(
        Output("code-type-store", "data"),
        [Input({"type": "code-type-btn", "index": ALL}, "n_clicks")],
        [State("code-type-store", "data")],
        prevent_initial_call=True,
    )
    def update_selected_code_type(n_clicks, current_value):
        ctx = dash.callback_context
        if not ctx.triggered:
            return no_update

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        try:
            val = json.loads(button_id)["index"]
            return val
        except:
            return no_update

    # Dynamic generation of Code Type buttons with counts
    @app.callback(
        Output("code-type-buttons-container", "children"),
        [
            Input("project-selector", "value"),
            Input("detection-method-radio", "value"),
            Input("comodification-filter", "value"),
            Input("service-scope-filter", "value"),
            Input("cross-service-filter", "value"),
            Input("code-type-store", "data"),
        ],
    )
    def update_code_type_counts(
        project_value,
        detection_method,
        comodified_val,
        service_scope,
        cross_service,
        active_code_type,
    ):
        if not project_value:
            return []

        # Parse project info similar to main callback
        try:
            project, commit, language = project_value.split("|||", 2)
        except:
            return []

        # Load data (should be cached)
        df, _, _ = load_and_process_data(project, commit, language)
        if df is None or df.empty:
            return []

        # Apply base filters (Method & Comodification & Scope) to count code types
        # 1. Method Filter
        df_filtered = df
        method_column = (
            "detection_method" if "detection_method" in df.columns else "clone_type"
        )
        if not method_column and "clone_type" in df.columns:
            method_column = "clone_type"

        if detection_method and detection_method != "all":
            target_method = detection_method

            # Map 'import' to 'no-import'
            if "detection_method" in df.columns or method_column:
                if target_method == "import":
                    df_filtered = df_filtered[
                        df_filtered[method_column]
                        .str.lower()
                        .isin(["import", "no-import"])
                    ]
                else:
                    df_filtered = df_filtered[
                        df_filtered[method_column].str.lower() == target_method
                    ]

        # 2. Comodification Filter
        comodified_filter = "all"
        if comodified_val == "yes":
            comodified_filter = "true"
        elif comodified_val == "no":
            comodified_filter = "false"

        if comodified_filter != "all" and "comodified" in df_filtered.columns:
            if comodified_filter == "true":
                df_filtered = df_filtered[df_filtered["comodified"].isin([True, 1])]
            else:
                df_filtered = df_filtered[~df_filtered["comodified"].isin([True, 1])]

        # 3. Service Scope Filter
        if service_scope and service_scope != "all":
            if "relation" in df_filtered.columns:
                if service_scope == "within":
                    df_filtered = df_filtered[df_filtered["relation"] == "intra"]
                elif service_scope == "cross":
                    df_filtered = df_filtered[df_filtered["relation"] == "inter"]
            else:
                # Fallback
                if service_scope == "within":
                    df_filtered = df_filtered[
                        df_filtered["service_x"] == df_filtered["service_y"]
                    ]
                elif service_scope == "cross":
                    df_filtered = df_filtered[
                        df_filtered["service_x"] != df_filtered["service_y"]
                    ]

        # 4. Cross Service Filter
        if (
            cross_service
            and cross_service != "all"
            and "clone_id" in df_filtered.columns
        ):
            try:
                selected_clone_id = int(str(cross_service))
                df_filtered = df_filtered[df_filtered["clone_id"] == selected_clone_id]
            except:
                pass

        # Count Code Types
        counts = {
            "all": len(df_filtered),
            "logic": 0,
            "data": 0,
            "test": 0,
            "config": 0,
            "mixed": 0,
        }

        # Prepare file type series
        if "file_type_x" in df_filtered.columns:
            series_x = df_filtered["file_type_x"]
            series_y = df_filtered["file_type_y"]
        else:
            # Fallback (resolve types manually)
            series_x = df_filtered["file_path_x"].apply(lambda x: get_file_type(str(x)))
            series_y = df_filtered["file_path_y"].apply(lambda x: get_file_type(str(x)))

        # 1. Test Pairs
        is_test_x = series_x == "test"
        is_test_y = series_y == "test"
        counts["test"] = ((is_test_x) & (is_test_y)).sum()

        # 2. Data Pairs
        is_data_pair = (series_x == "data") & (series_y == "data")
        counts["data"] = is_data_pair.sum()

        # 3. Config Pairs
        is_config_pair = (series_x == "config") & (series_y == "config")
        counts["config"] = is_config_pair.sum()

        # 4. Mixed Pairs (Test vs Non-Test)
        # Note: Logic in main filter is: `is_test_x != is_test_y`
        counts["mixed"] = (is_test_x != is_test_y).sum()

        # 5. Logic Pairs
        # Logic = Product-Product (logic/data/config) excluding pure Data and pure Config
        product_types = ["logic", "data", "config"]
        is_product_x = series_x.isin(product_types)
        is_product_y = series_y.isin(product_types)
        is_product_pair = is_product_x & is_product_y

        # Ensure we don't double count Data or Config pairs in Logic
        # Logic includes Logic-Logic, Logic-Data, Logic-Config, Data-Config etc.
        # But excludes Data-Data and Config-Config
        is_logic_pair = is_product_pair & ~is_data_pair & ~is_config_pair
        counts["logic"] = is_logic_pair.sum()

        # Generate Buttons
        buttons = []
        # Order: All, Logic, Data, Mixed, Test, Config
        order = ["all", "logic", "data", "mixed", "test", "config"]

        for type_key in order:
            btn = create_code_type_button(
                type_key.capitalize(),
                counts.get(type_key, 0),
                type_key,
                active_code_type or "all",
            )
            buttons.append(btn)

        return buttons

    # Update cross-service filter options based on project data (Filtered)
    @app.callback(
        Output("cross-service-filter", "options"),
        [
            Input("project-selector", "value"),
            Input("detection-method-radio", "value"),
            Input("comodification-filter", "value"),
            Input("service-scope-filter", "value"),
            Input("code-type-store", "data"),
        ],
    )
    def update_cross_service_options(
        project_value, detection_method, comodified_val, service_scope, code_type_filter
    ):
        if not project_value:
            return [{"label": "All", "value": "all"}]
        try:
            if "|||" in project_value:
                project, commit, language = project_value.split("|||", 2)
            else:
                return [{"label": "All", "value": "all"}]

            # Reuse load_and_process_data (it is cached)
            df, _, _ = load_and_process_data(project, commit, language)

            if df is None or df.empty:
                return [{"label": "All", "value": "all"}]

            # --- 1. Base Filtering (Method) ---
            # Apply Method filter first to get the universe of clones for this detection method.
            df_method = df

            # Method Filter
            method_column = (
                "detection_method" if "detection_method" in df.columns else "clone_type"
            )
            if not method_column and "clone_type" in df.columns:
                method_column = "clone_type"

            if detection_method and detection_method != "all":
                if "detection_method" in df.columns or method_column:
                    # Robust string conversion for filtering
                    dtype_name = df_method[method_column].dtype.name
                    if dtype_name == "object" or dtype_name == "category":
                        try:
                            col_str = df_method[method_column].astype(str).str.lower()
                            if detection_method == "import":
                                df_method = df_method[
                                    col_str.isin(["import", "no-import"])
                                ]
                            else:
                                df_method = df_method[
                                    col_str == detection_method.lower()
                                ]
                        except Exception:
                            pass  # Skip filter on error

            if df_method.empty:
                return [
                    {
                        "label": "No matching clones",
                        "value": "all",
                    }
                ]

            # --- 1.5 Code Type Filter ---
            if (
                code_type_filter
                and code_type_filter != "all"
                and "file_type_x" in df_method.columns
            ):
                if code_type_filter == "data":
                    df_method = df_method[
                        (df_method["file_type_x"] == "data")
                        & (df_method["file_type_y"] == "data")
                    ]
                elif code_type_filter == "logic":
                    product_types = ["logic", "data", "config"]
                    is_product_x = df_method["file_type_x"].isin(product_types)
                    is_product_y = df_method["file_type_y"].isin(product_types)
                    is_data_pair = (df_method["file_type_x"] == "data") & (
                        df_method["file_type_y"] == "data"
                    )
                    is_config_pair = (df_method["file_type_x"] == "config") & (
                        df_method["file_type_y"] == "config"
                    )
                    df_method = df_method[
                        is_product_x & is_product_y & ~is_data_pair & ~is_config_pair
                    ]
                elif code_type_filter == "test":
                    df_method = df_method[
                        (df_method["file_type_x"] == "test")
                        & (df_method["file_type_y"] == "test")
                    ]
                elif code_type_filter == "config":
                    df_method = df_method[
                        (df_method["file_type_x"] == "config")
                        & (df_method["file_type_y"] == "config")
                    ]
                elif code_type_filter == "mixed":
                    is_test_x = df_method["file_type_x"] == "test"
                    is_test_y = df_method["file_type_y"] == "test"
                    df_method = df_method[is_test_x != is_test_y]

            if df_method.empty:
                return [
                    {
                        "label": "No matching clones",
                        "value": "all",
                    }
                ]

            # --- 2. Comodification Filter (Selection Phase) ---
            # We select IDs that *contain* at least one pair satisfying the comodification condition.
            # This implements "Plan B": Filter at the clone level, not the pair level.

            comodified_filter = "all"
            if comodified_val == "yes":
                comodified_filter = "true"
            elif comodified_val == "no":
                comodified_filter = "false"

            valid_clone_ids = df_method["clone_id"].unique()

            if comodified_filter != "all" and "comodified" in df_method.columns:
                if comodified_filter == "true":
                    # Valid clones must have at least one comodified pair
                    valid_ids_series = df_method.loc[
                        df_method["comodified"].isin([True, 1]), "clone_id"
                    ]
                    valid_clone_ids = valid_ids_series.unique()
                else:
                    # Valid clones must have at least one non-comodified pair (or ONLY non-comodified? Use strict "NO" logic?)
                    # Usually "No" means "Show things that are NOT comodified".
                    # If a clone has mixed (some yes, some no), usually it's considered "Has Comodification".
                    # If the user wants "No Co-modification", they probably want to see clones that are completely clean or just the pairs that aren't.
                    # However, to be consistent with "Yes" logic (Existence), let's assume strict filtering for "No" might be too harsh if we do "Only No".
                    # Let's simple filter the pairs first, then get IDs.
                    # Actually, to align with the user request "Interlock with Simultaneous Modification",
                    # if I choose "YES", I want clones that are being modified together.
                    # If I choose "NO", I want clones that are NOT being modified together.
                    ids_with_comod = df_method.loc[
                        df_method["comodified"].isin([True, 1]), "clone_id"
                    ].unique()
                    if comodified_filter == "true":
                        valid_clone_ids = ids_with_comod
                    else:
                        # Exclude clones that have ANY comodification? Or just include IDs present in the 'false' set?
                        # Let's stick to the previous simple logic:
                        # Filter rows matching condition -> Get IDs.
                        # This means if I pick "NO", I look for pairs with NO comodification.
                        # If a clone has 5 pairs, 1 Yes, 4 No.
                        # "Yes" filter -> finds the 1 pair -> ID matches -> Show Clone (3 services).
                        # "No" filter -> finds the 4 pairs -> ID matches -> Show Clone (3 services).
                        # This seems acceptable. It effectively says "Show me clones involving this type of behavior".
                        valid_ids_series = df_method.loc[
                            ~df_method["comodified"].isin([True, 1]), "clone_id"
                        ]
                        valid_clone_ids = valid_ids_series.unique()

            if len(valid_clone_ids) == 0:
                return [
                    {
                        "label": "No matching clones",
                        "value": "all",
                    }
                ]

            # --- 3. Calculate "Many Services" Status (Global Context) ---
            # We use ALL pairs derived from the valid IDs (from df_method) to count services.
            # This ensures that even if the "Comodified" pairs are all within Service A,
            # if the clone also has pairs in Service B (which were not comodified),
            # the clone counts as satisfying "Many Services".

            df_candidates = df_method[df_method["clone_id"].isin(valid_clone_ids)]

            if "clone_id" not in df_candidates.columns:
                return [{"label": "All", "value": "all"}]

            s1_df = df_candidates[["clone_id", "service_x"]].rename(
                columns={"service_x": "service"}
            )
            s2_df = df_candidates[["clone_id", "service_y"]].rename(
                columns={"service_y": "service"}
            )
            services_df = pd.concat([s1_df, s2_df])

            # Count unique services per clone_id
            service_counts = services_df.groupby("clone_id")["service"].nunique()

            # Identify "Many Service" Clones (>= 2)
            # We DO NOT filter by Scope here, as per user request.
            # "Many Services" clones should be visible even if Scope is "Within".
            many_service_clones_series = service_counts[
                service_counts >= 2
            ].sort_values(ascending=False)

            # Limit to top 200
            final_target = many_service_clones_series.head(200)
            top_ids = final_target.index.tolist()

            if not top_ids:
                return [
                    {
                        "label": "No matching clones",
                        "value": "all",
                    }
                ]

            # Retrieve Code Types for these IDs (Using df_candidates or df_method)
            df_stats_source = df_method[df_method["clone_id"].isin(top_ids)]

            clone_stats = []

            if "file_type_x" in df_stats_source.columns:
                # Group by clone_id and determine type
                for cid in top_ids:
                    subset = df_stats_source[df_stats_source["clone_id"] == cid]
                    if subset.empty:
                        continue

                    types_x = subset["file_type_x"].astype(str)
                    types_y = subset["file_type_y"].astype(str)
                    all_types = set(types_x) | set(types_y)

                    if "test" in all_types and len(all_types - {"test"}) > 0:
                        ctype = "Mixed"
                    elif len(all_types) == 1:
                        ctype = list(all_types)[0].capitalize()
                    elif "logic" in all_types:
                        ctype = "Logic"
                    else:
                        ctype = "Mixed"

                    clone_stats.append(
                        {
                            "clone_id": int(cid),
                            "service_count": final_target[cid],
                            "code_type": ctype,
                        }
                    )
            else:
                # Fallback for old data without file types
                for cid in top_ids:
                    clone_stats.append(
                        {
                            "clone_id": int(cid),
                            "service_count": final_target[cid],
                            "code_type": "Unknown",
                        }
                    )

            options = generate_cross_service_filter_options(clone_stats)
            return options
        except Exception as e:
            logger.error("Error updating cross service options: %s", e)
            return [{"label": "All", "value": "all"}]

    # ── Help Modal ──
