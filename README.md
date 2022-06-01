# README - WSGI

This folder contains a WSGI application intended for use with uWSGI (`threeparty.py`), and corresponding configuration files.

The script assumes the presence of a copy of this repository in the static website serve path `/var/www/SITE_NAME.tld/html/FOO`, such that
- `https://SITE_NAME.tld/FOO/index.html` is where the requests come from
  - (i.e. `create-index.py`'s `--site-root` is `https://SITE_NAME.tld/FOO`)

## Setup (for recent Debian/Ubuntu)

Install the server-specific packages (or perhaps ensure they're installed):

    sudo apt-get install nginx uwsgi

(N.B.: I tried using a `virtualenv` and it was a bit of a mess, so everything is system-installed.)

Create a service directory:

    sudo mkdir /etc/threeparty

Copy the WSGI-related files from this subdirectory of the repository to the service directory:

    sudo cp -r /PATH/TO/threeparty/ /etc/threeparty

Copy the `threeparty.service.conf` where it needs to be, then edit if required:

    sudo cp /etc/threeparty/threeparty.service.conf /etc/systemd/system/threeparty.service
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


# TODO

* points of interest that work over the web