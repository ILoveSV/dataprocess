import pandas as pd

from src.io.time_csv_io import collect_csv_files, read_csv_data


def test_time_csv_io_smoke(tmp_path):
    data_path = tmp_path / "sample.csv"
    pd.DataFrame({
        'time': [0.0, 0.1],
        'channel1': [1.0, 2.0],
        'channel2': [3.0, 4.0],
    }).to_csv(data_path, index=False)
    (tmp_path / "time_series_metrics.xlsx").write_text("not csv")

    df, time_column, channel_columns = read_csv_data(data_path)
    assert time_column == 'time'
    assert channel_columns == ['channel1', 'channel2']
    assert len(df) == 2
    assert collect_csv_files(tmp_path) == [data_path]

