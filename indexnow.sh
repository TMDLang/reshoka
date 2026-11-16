#!/bin/bash

BING_DATA='{"host": "http://tmdlang.github.io/","key": "ac4600a8be534d9b9ab457fc7ae9039a","keyLocation": "http://tmdlang.github.io/ac4600a8be534d9b9ab457fc7ae9039a.txt", "urlList": ["https://tmdlang.github.io/reshoka"]}'

curl --verbose --header "Content-Type: application/json" --data "$BING_DATA" https://www.bing.com/indexnow

YANDEX_DATA='{"host": "http://tmdlang.github.io/","key": "EdD8dkmdNLlxREi2LkhJjYOH2kyQbJqM3cBKT5fX","keyLocation": "http://tmdlang.github.io/EdD8dkmdNLlxREi2LkhJjYOH2kyQbJqM3cBKT5fX.txt", "urlList": ["https://tmdlang.github.io/reshoka"]}'

curl --verbose --header "Content-Type: application/json" --data "$YANDEX_DATA" https://www.yandex.com/indexnow
