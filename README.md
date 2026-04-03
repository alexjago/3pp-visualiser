# 3PP Visualiser

As 3PP contests become more relevant, a need arises for analysis tools.

This repo contains:

- a Python SVG generator (`visualise.py`)
- a WSGI endpoint (`threeparty.py`)
- a Jekyll page wrapper (`index.md`) that includes the interactive form (`form.html`)

## Using the script locally

Download and run `visualise.py`. There are no dependencies other than modern Python 3. 

### Matchup and flow parameters

The generator now supports configurable party labels/colours using canonical `x/y/z` roles:

- `x`: X-axis party
- `y`: Y-axis party
- `z`: balance party (`1 - (x + y)`)

#### Canonical parameters

- Party names: `x_name`, `y_name`, `z_name`
- Party colours: `x_colour`, `y_colour`, `z_colour` (hex, eg `#0088ee`)
- Flows: `x_to_y`, `x_to_z`, `y_to_x`, `y_to_z`, `z_to_x`, `z_to_y`

Defaults remain equivalent to the original setup:

- `x = Coalition`, `y = Greens`, `z = Labor`
- `x_to_y=0.3`, `x_to_z=0.7`
- `y_to_x=0.2`, `y_to_z=0.8`
- `z_to_x=0.2`, `z_to_y=0.8`

#### Backward compatibility aliases

Legacy flow parameter names are still accepted:

- `blue_to_green -> x_to_y`
- `blue_to_red -> x_to_z`
- `green_to_blue -> y_to_x`
- `green_to_red -> y_to_z`
- `red_to_blue -> z_to_x`
- `red_to_green -> z_to_y`

If both canonical and legacy forms are supplied, canonical `x/y/z` values take precedence.

#### Examples

CLI:

    python3 visualise.py --x-name "Coalition" --y-name "Greens" --z-name "Labor" --x-to-y 0.3 --x-to-z 0.7 --y-to-x 0.2 --y-to-z 0.8 --z-to-x 0.2 --z-to-y 0.8 > out.svg

WSGI/query string:

    /wsgi?x_name=Coalition&y_name=Greens&z_name=Labor&x_colour=%230088ee&y_colour=%2300aa22&z_colour=%23dd0044&x_to_y=0.3&x_to_z=0.7&y_to_x=0.2&y_to_z=0.8&z_to_x=0.2&z_to_y=0.8

### Points of interest over the web

Points of interest (POIs) work in the hosted form and directly via query params.

- Repeated params are supported:
  - `px`: X value
  - `py`: Y value
  - `pl`: label
- Each row is formed by matching the same index across `px[]`, `py[]`, `pl[]`.
- POIs are shown as outlined markers with tooltip details and winner estimate.

Example:

    /wsgi?x_to_y=0.3&x_to_z=0.7&y_to_x=0.2&y_to_z=0.8&z_to_x=0.2&z_to_y=0.8&px=0.43&py=0.33&pl=Ryan%202022&px=0.36&py=0.29&pl=Brisbane%20sample

Note: the web form accepts percentages, but converts them to decimal ratios (`0..1`) before request.

# README - WSGI

This folder contains a WSGI application intended for use with uWSGI (`threeparty.py`), and corresponding configuration files.

The script assumes the presence of a copy of this repository in the static website serve path `/var/www/SITE_NAME.tld/html/FOO`, such that
- `https://SITE_NAME.tld/FOO/index.html` is where the requests come from
  - (i.e. `create-index.py`'s `--site-root` is `https://SITE_NAME.tld/FOO`)

## Setup (for recent Debian/Ubuntu)

An NGINX sample server config is provided (further details of NGINX setup are beyond the scope of this project):

    sudo apt-get install nginx 

On Ubuntu 22.04 as of November 2022, the "system" version of uWSGI needs Python 3.8 but the OS ships with 3.10. 
Thus a virtualenv is needed.

Create a service directory, initialise a virtualenv, activate it and then install latest uWSGI:

    sudo mkdir /opt/threeparty && cd /opt/threeparty
    sudo python3 -m venv ./env
    source ./env/bin/activate
    sudo ./env/bin/pip install uwsgi

Note: it's critical that you use `./env/bin/pip` for the final step, not just `pip`; otherwise the package will be system-installed.

Copy the WSGI-related files from this subdirectory of the repository to the service directory:

    sudo cp -r /PATH/TO/COPY/OF/threeparty/ /opt/threeparty

Copy the `threeparty.service.conf` where it needs to be, then edit if required:

    sudo cp /opt/threeparty/threeparty.service.conf /etc/systemd/system/threeparty.service
    sudo nano /etc/systemd/system/threeparty.service

Enable and activate:

    sudo systemctl enable --now threeparty

Test if it all started OK with `systemctl status threeparty`.

Meanwhile, in your NGINX config you'll need at least the following:

	location /FOO/wsgi {
		include uwsgi_params;
		uwsgi_pass unix:///run/uwsgi/threeparty.sock;
	}

N.B: `/FOO` should be as above. It also might not exist, in which case you'd just have `https://SITE_NAME.tld/index.html` and `location /wsgi {`, etc.

A full sample configuration is in `nginx.conf`.

If you're running this on its own subdomain then you can *probably* just go:

    sudo cp nginx.conf /etc/nginx/sites-available/SITE_NAME.TLD
    sudo nano /etc/nginx/sites-available/SITE_NAME.TLD
    sudo ln -s /etc/nginx/sites-available/SITE_NAME.TLD /etc/nginx/sites-enabled/SITE_NAME.TLD

Test your configuration with `sudo nginx -t` and then reload to activate:

    sudo systemctl reload nginx

You should now be able to use the site. (If not, the log file location is specified in the `.ini`)
