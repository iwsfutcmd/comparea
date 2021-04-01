#!/usr/bin/env python3

import comparea

def run():
    comparea.app.run(host='0.0.0.0', port=comparea.app.config['PORT'])

if __name__ == '__main__':
    run()
