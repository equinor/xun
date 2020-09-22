#!/usr/bin/env python3

from PIL import Image
from wordcloud import WordCloud, ImageColorGenerator
import argparse
import cv2
import json
import numpy as np
import re
import requests
import subprocess
import xun


url = 'https://en.wikipedia.org/w/api.php'
cleanr = re.compile('<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6})|parser|MW|template|output;')


@xun.make_shared
def remove_html(html):
    cleantext = re.sub(cleanr, '', html)
    return cleantext


@xun.function()
def download_text(topic):
    params = {
        'action': 'parse',
        'prop':   'text',
        'format': 'json',
        'page':   topic,
    }
    response = requests.get(url, params=params, verify=False)

    j = json.loads(response.text)
    text = j['parse']['text']['*']

    cleaned = remove_html(text)
    return cleaned


@xun.function()
def fetch_image_url(topic):
    params = {
        'action': 'query',
        'prop':   'pageimages',
        'format': 'json',
        'piprop': 'original',
        'titles': topic,
    }
    response = requests.get(url, params=params, verify=False)

    j = json.loads(response.text)
    img_info = next(iter(j['query']['pages'].values()))
    img_url = img_info['original']['source']

    return img_url


@xun.function()
def download_image(topic):
    with ...:
        img_url = fetch_image_url(topic)

    file_name = img_url.split('/')[-1]
    subprocess.run(['curl', '-o', file_name, img_url], check=True)

    return file_name


@xun.function()
def wordcloud(topic, max_resolution=512):
    raw_image = np.array(Image.open(image_path))
    scale = min(1.0, max_resolution / max(raw_image.shape))
    shape = (int(raw_image.shape[1] * scale),
             int(raw_image.shape[0] * scale))
    image = cv2.resize(raw_image,
                       dsize=shape,
                       interpolation=cv2.INTER_CUBIC)

    image_colors = ImageColorGenerator(image)

    wordcloud_generator = WordCloud(mask=image,
                                    max_words=4096,
                                    mode='RGB',
                                    repeat=True,)
    wordcloud = wordcloud_generator.generate(text)
    colored = wordcloud.recolor(color_func=image_colors)

    import matplotlib.pyplot as plt

    # show
    plt.style.use('dark_background')

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    axes[0].imshow(colored, interpolation="bilinear")
    axes[1].imshow(image, cmap=plt.cm.gray, interpolation="bilinear")
    for ax in axes:
        ax.set_axis_off()
    plt.show()

    with ...:
        text = download_text(topic)
        image_path = download_image(topic)


def main():
    parser = argparse.ArgumentParser(
        description='Generate wordclouds from wikipedia topics!',
    )
    parser.add_argument(
        '--topic',
        help=(
            'The topic the wordcloud will be generated from. '
            'Example: Astronaut'
        ),
        default='Astronaut'
    )
    parser.add_argument(
        '--max_resolution',
        help=(
            'Maximum vertical or horizontal resolution of the image. '
            'Images larger than the given value will be scaled down.'
        ),
        type=int,
        default=512
    )

    args = parser.parse_args()

    wordcloud.blueprint(args.topic, max_resolution=args.max_resolution).run(
        driver=xun.functions.driver.Sequential(),
        store=xun.functions.store.Memory(),
    )


if __name__ == '__main__':
    main()
