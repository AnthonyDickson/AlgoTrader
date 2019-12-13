import datetime
import json
import plac


def normalise(data):
    if 'technicals' in data:
        container_name = 'technicals'
    elif 'stock_prices' in data:
        container_name = 'stock_prices'
    else:
        raise AttributeError('JSON data does not contain an expected property ("technicals", "stock_prices").')

    data['container_name'] = container_name
    data['elements'] = data[container_name]
    del data[container_name]

    if len(data['elements']) == 0:
        return
    elif 'date' in data['elements'][0] and 'date_time' not in data['elements'][0]:
        for i in range(len(data['elements'])):
            date_time = datetime.datetime.fromisoformat(data['elements'][i]['date'])
            date_time = date_time.replace(tzinfo=None)
            data['elements'][i]['date_time'] = date_time

            del data['elements'][i]['date']
    elif 'date_time' in data['elements'][0] and 'date' not in data['elements'][0]:
        for i in range(len(data['elements'])):
            date_time = datetime.datetime.fromisoformat(data['elements'][i]['date_time'])
            date_time = date_time.replace(tzinfo=None)
            data['elements'][i]['date_time'] = date_time


def main(file_path1: ("The path to the first file"), file_path2: ("The path to the second file")):
    """Joins two JSON files by date."""
    if not (file_path1.endswith('.json') and file_path2.endswith('.json')):
        raise ValueError('Input files must a JSON formatted file with the ".json" extension.')

    with open(file_path1, 'r') as file:
        left = json.load(file)

    with open(file_path2, 'r') as file:
        right = json.load(file)

    if left['security']['ticker'] != right['security']['ticker']:
        raise ValueError("JSON files should both contain data for the same ticker.")

    normalise(left)
    normalise(right)

    merged = dict()
    merged.update(left)
    merged.update(right)

    for i, (a, b) in enumerate(zip(left['elements'], right['elements'])):
        assert a['date_time'] == b['date_time'], 'Dates misaligned.'

        merged['elements'][i].update(a)
        merged['elements'][i].update(b)

    merged = {key: merged[key] for key in ['security', 'elements']}

    print(json.dumps(merged, default=str))


if __name__ == '__main__':
    plac.call(main)