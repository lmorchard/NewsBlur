from fabric.api import abort, cd, env, get, hide, hosts, local, prompt
from fabric.api import put, require, roles, run, runs_once, settings, show, sudo, warn
from fabric.colors import red, green, blue, cyan, magenta, white, yellow
try:
    from boto.s3.connection import S3Connection
    from boto.s3.key import Key
except ImportError:
    print " ---> Boto not installed yet. No S3 connections available."
from fabric.contrib import django
import os, sys

django.settings_module('settings')
try:
    from django.conf import settings as django_settings
except ImportError:
    print " ---> Django not installed yet."
    django_settings = None


# ============
# = DEFAULTS =
# ============

env.NEWSBLUR_PATH = "~/projects/newsblur"
env.VENDOR_PATH   = "~/projects/code"

# =========
# = Roles =
# =========

env.user = 'sclay'
env.roledefs ={
    'local': ['localhost'],
    'app': ['app01.newsblur.com', 'app02.newsblur.com'],
    'web': ['www.newsblur.com', 'app02.newsblur.com'],
    'db': ['db01.newsblur.com', 'db02.newsblur.com'],
    'task': ['task01.newsblur.com', 'task02.newsblur.com', 'task03.newsblur.com'],
}

# ================
# = Environments =
# ================

def server():
    env.NEWSBLUR_PATH = "~/newsblur"
    env.VENDOR_PATH   = "~/code"

def app():
    server()
    env.roles = ['app']

def web():
    server()
    env.roles = ['web']

def db():
    server()
    env.roles = ['db']
    
def task():
    server()
    env.roles = ['task']
    
# ==========
# = Deploy =
# ==========

def pull():
    with cd(env.NEWSBLUR_PATH):
        run('git pull')
    
def deploy():
    with cd(env.NEWSBLUR_PATH):
        run('git pull')
        run('kill -HUP `cat logs/gunicorn.pid`')
        run('curl -s http://www.newsblur.com > /dev/null')
        run('curl -s http://www.newsblur.com/m/ > /dev/null')
        run('curl -s http://www.newsblur.com/api/add_site_load_script/ABCDEF > /dev/null')
        compress_media()

@roles('web')
def deploy_full():
    with cd(env.NEWSBLUR_PATH):
        run('git pull')
        run('./manage.py migrate')
        with settings(warn_only=True):
            run('sudo supervisorctl restart gunicorn')
        run('curl -s http://www.newsblur.com > /dev/null')
        run('curl -s http://www.newsblur.com/m/ > /dev/null')
        compress_media()

@roles('web')
def restart_gunicorn():
    with cd(env.NEWSBLUR_PATH):
        with settings(warn_only=True):
            run('sudo supervisorctl restart gunicorn')
        
@roles('web')
def staging():
    with cd('~/staging'):
        run('git pull')
        run('kill -HUP `cat logs/gunicorn.pid`')
        run('curl -s http://dev.newsblur.com > /dev/null')
        run('curl -s http://dev.newsblur.com/m/ > /dev/null')
        compress_media()

@roles('web')
def staging_full():
    with cd('~/staging'):
        run('git pull')
        run('./manage.py migrate')
        run('kill -HUP `cat logs/gunicorn.pid`')
        run('curl -s http://dev.newsblur.com > /dev/null')
        run('curl -s http://dev.newsblur.com/m/ > /dev/null')
        compress_media()

@roles('task')
def celery():
    with cd(env.NEWSBLUR_PATH):
        run('git pull')
    celery_stop()
    celery_start()

@roles('task')
def celery_stop():
    with cd(env.NEWSBLUR_PATH):
        run('sudo supervisorctl stop celery')
        with settings(warn_only=True):
            run('./utils/kill_celery.sh')

@roles('task')
def celery_start():
    with cd(env.NEWSBLUR_PATH):
        run('sudo supervisorctl start celery')
        run('tail logs/newsblur.log')

@roles('task')
def kill_celery():
    with cd(env.NEWSBLUR_PATH):
        run('ps aux | grep celeryd | egrep -v grep | awk \'{print $2}\' | sudo xargs kill -9')

def compress_media():
    with cd('media/js'):
        run('rm -f *.gz')
        run('for js in *-compressed-*.js; do gzip -9 $js -c > $js.gz; done;')
    with cd('media/css/mobile'):
        run('rm -f *.gz')
        run('for css in *-compressed-*.css; do gzip -9 $css -c > $css.gz; done;')
    with cd('media/css'):
        run('rm -f *.gz')
        run('for css in *-compressed-*.css; do gzip -9 $css -c > $css.gz; done;')
        
# ===========
# = Backups =
# ===========

@roles('app')
def backup_mongo():
    with cd(os.path.join(env.NEWSBLUR_PATH, 'utils/backups')):
        run('./mongo_backup.sh')

@roles('db')
def backup_postgresql():
    with cd(os.path.join(env.NEWSBLUR_PATH, 'utils/backups')):
        run('./postgresql_backup.sh')

# =============
# = Bootstrap =
# =============

def setup_common():
    setup_installs()
    setup_user()
    setup_repo()
    setup_repo_local_settings()
    setup_local_files()
    setup_libxml()
    setup_python()
    setup_psycopg()
    setup_supervisor()
    setup_hosts()
    config_pgbouncer()
    setup_mongoengine()
    setup_forked_mongoengine()
    setup_pymongo_repo()
    setup_logrotate()
    setup_sudoers()
    setup_nginx()
    configure_nginx()

def setup_app():
    setup_common()
    setup_app_firewall()
    setup_app_motd()
    setup_gunicorn(supervisor=True)
    update_gunicorn()

def setup_db():
    setup_common()
    setup_db_firewall()
    setup_db_motd()
    setup_rabbitmq()
    setup_postgres()
    setup_mongo()

def setup_task():
    setup_common()
    setup_task_firewall()
    setup_task_motd()
    enable_celery_supervisor()
    setup_gunicorn(supervisor=False)
    update_gunicorn()
    config_monit()

# ==================
# = Setup - Common =
# ==================
    
def setup_installs():
    sudo('apt-get -y update')
    sudo('apt-get -y upgrade')
    sudo('apt-get -y install build-essential gcc scons libreadline-dev sysstat iotop git zsh python-dev locate python-software-properties libpcre3-dev libdbd-pg-perl libssl-dev make pgbouncer python-psycopg2 libmemcache0 memcached python-memcache libyaml-0-2 python-yaml python-numpy python-scipy python-imaging munin munin-node munin-plugins-extra curl ntp monit')
    sudo('add-apt-repository ppa:pitti/postgresql')
    sudo('apt-get -y update')
    sudo('apt-get -y install postgresql-client-9.0')
    sudo('mkdir -p /var/run/postgresql')
    sudo('chown postgres.postgres /var/run/postgresql')
    put('config/munin.conf', '/etc/munin/munin.conf', use_sudo=True)
    with settings(warn_only=True):
        run('git clone git://github.com/robbyrussell/oh-my-zsh.git ~/.oh-my-zsh')
    run('curl -O http://peak.telecommunity.com/dist/ez_setup.py')
    sudo('python ez_setup.py -U setuptools && rm ez_setup.py')
    sudo('chsh sclay -s /bin/zsh')
    run('mkdir -p %s' % env.VENDOR_PATH)
    
def setup_user():
    # run('useradd -c "NewsBlur" -m conesus -s /bin/zsh')
    # run('openssl rand -base64 8 | tee -a ~conesus/.password | passwd -stdin conesus')
    run('mkdir -p ~/.ssh && chmod 700 ~/.ssh')
    run('rm -fr ~/.ssh/id_dsa*')
    run('ssh-keygen -t dsa -f ~/.ssh/id_dsa -N ""')
    run('touch ~/.ssh/authorized_keys')
    put("~/.ssh/id_dsa.pub", "authorized_keys")
    run('mv authorized_keys ~/.ssh/')
    
def add_machine_to_ssh():
    put("~/.ssh/id_dsa.pub", "local_keys")
    run("echo `cat local_keys` >> .ssh/authorized_keys")
    
def setup_repo():
    with settings(warn_only=True):
        run('git clone https://github.com/samuelclay/NewsBlur.git newsblur')

def setup_repo_local_settings():
    with cd(env.NEWSBLUR_PATH):
        run('cp local_settings.py.template local_settings.py')
        run('mkdir -p logs')
        run('touch logs/newsblur.log')

def setup_local_files():
    put("config/toprc", "./.toprc")
    put("config/zshrc", "./.zshrc")
    put('config/gitconfig.txt', './.gitconfig')
    put('config/ssh.conf', './.ssh/config')

def setup_libxml():
    sudo('apt-get -y install libxml2-dev libxslt1-dev python-lxml')

def setup_libxml_code():
    with cd(env.VENDOR_PATH):
        run('git clone git://git.gnome.org/libxml2')
        run('git clone git://git.gnome.org/libxslt')
    
    with cd(os.path.join(env.VENDOR_PATH, 'libxml2')):
        run('./configure && make && sudo make install')
        
    with cd(os.path.join(env.VENDOR_PATH, 'libxslt')):
        run('./configure && make && sudo make install')

def setup_psycopg():
    sudo('easy_install psycopg2')
    
def setup_python():
    sudo('easy_install pip')
    sudo('easy_install fabric django celery django-celery django-compress South django-extensions pymongo BeautifulSoup pyyaml nltk==0.9.9 lxml oauth2 pytz boto seacucumber')
    
    put('config/pystartup.py', '.pystartup')
    with cd(os.path.join(env.NEWSBLUR_PATH, 'vendor/cjson')):
        sudo('python setup.py install')
        
    with settings(warn_only=True):
        sudo('su -c \'echo "import sys; sys.setdefaultencoding(\\\\"utf-8\\\\")" > /usr/lib/python2.6/sitecustomize.py\'')

# PIL - Only if python-imaging didn't install through apt-get, like on Mac OS X.
def setup_imaging():
    sudo('easy_install pil')
    
def setup_supervisor():
    sudo('apt-get -y install supervisor')
    
def setup_hosts():
    put('config/hosts', '/etc/hosts', use_sudo=True)

def config_pgbouncer():
    put('config/pgbouncer.conf', '/etc/pgbouncer/pgbouncer.ini', use_sudo=True)
    # put('config/pgbouncer_userlist.txt', '/etc/pgbouncer/userlist.txt', use_sudo=True)
    # sudo('echo "START=1" > /etc/default/pgbouncer')
    sudo('/etc/init.d/pgbouncer stop')
    with settings(warn_only=True):
        sudo('pkill pgbouncer')
    sudo('/etc/init.d/pgbouncer start')
    
def config_monit():
    # sudo('apt-get install -y monit')
    put('config/monit.conf', '/etc/monit/conf.d/celery.conf', use_sudo=True)
    sudo('echo "startup=1" > /etc/default/monit')
    sudo('/etc/init.d/monit restart')
    
def setup_mongoengine():
    with cd(env.VENDOR_PATH):
        with settings(warn_only=True):
            run('rm -fr mongoengine')
            run('git clone https://github.com/hmarr/mongoengine.git')
            sudo('rm -f /usr/local/lib/python2.6/site-packages/mongoengine')
            sudo('ln -s %s /usr/local/lib/python2.6/site-packages/mongoengine' % 
                 os.path.join(env.VENDOR_PATH, 'mongoengine/mongoengine'))
    with cd(os.path.join(env.VENDOR_PATH, 'mongoengine')):
        run('git checkout -b dev origin/dev')
        
def setup_pymongo_repo():
    with cd(env.VENDOR_PATH):
        with settings(warn_only=True):
            run('git clone git://github.com/mongodb/mongo-python-driver.git pymongo')
    with cd(os.path.join(env.VENDOR_PATH, 'pymongo')):
        sudo('python setup.py install')
        
def setup_forked_mongoengine():
    with cd(os.path.join(env.VENDOR_PATH, 'mongoengine')):
        with settings(warn_only=True):
            run('git remote add github http://github.com/samuelclay/mongoengine')
            run('git checkout dev')
            run('git pull github dev')

def switch_forked_mongoengine():
    with cd(os.path.join(env.VENDOR_PATH, 'mongoengine')):
        run('git co dev')
        run('git pull github dev --force')
        # run('git checkout .')
        # run('git checkout master')
        # run('get branch -D dev')
        # run('git checkout -b dev origin/dev')
        
def setup_logrotate():
    put('config/logrotate.conf', '/etc/logrotate.d/newsblur', use_sudo=True)
    
def setup_sudoers():
    sudo('su - root -c "echo \\\\"sclay ALL=(ALL) NOPASSWD: ALL\\\\" >> /etc/sudoers"')

def setup_nginx():
    with cd(env.VENDOR_PATH):
        with settings(warn_only=True):
            sudo("groupadd nginx")
            sudo("useradd -g nginx -d /var/www/htdocs -s /bin/false nginx")
            run('wget http://sysoev.ru/nginx/nginx-0.9.5.tar.gz')
            run('tar -xzf nginx-0.9.5.tar.gz')
            run('rm nginx-0.9.5.tar.gz')
            with cd('nginx-0.9.5'):
                run('./configure --with-http_ssl_module --with-http_stub_status_module --with-http_gzip_static_module')
                run('make')
                sudo('make install')
            
def configure_nginx():
    put("config/nginx.conf", "/usr/local/nginx/conf/nginx.conf", use_sudo=True)
    sudo("mkdir -p /usr/local/nginx/conf/sites-enabled")
    sudo("mkdir -p /var/log/nginx")
    put("config/nginx.newsblur.conf", "/usr/local/nginx/conf/sites-enabled/newsblur.conf", use_sudo=True)
    put("config/nginx-init", "/etc/init.d/nginx", use_sudo=True)
    sudo("chmod 0755 /etc/init.d/nginx")
    sudo("/usr/sbin/update-rc.d -f nginx defaults")
    sudo("/etc/init.d/nginx restart")
    
# ===============
# = Setup - App =
# ===============

def setup_app_firewall():
    sudo('ufw default deny')
    sudo('ufw allow ssh')
    sudo('ufw allow 80')
    sudo('ufw --force enable')

def setup_app_motd():
    put('config/motd_app.txt', '/etc/motd.tail', use_sudo=True)

def setup_gunicorn(supervisor=True):
    if supervisor:
        put('config/supervisor_gunicorn.conf', '/etc/supervisor/conf.d/gunicorn.conf', use_sudo=True)
    with cd(env.VENDOR_PATH):
        sudo('rm -fr gunicorn')
        run('git clone git://github.com/benoitc/gunicorn.git')
    with cd(os.path.join(env.VENDOR_PATH, 'gunicorn')):
        run('git pull')
        sudo('python setup.py develop')
        

def update_gunicorn():
    with cd(os.path.join(env.VENDOR_PATH, 'gunicorn')):
        run('git pull')
        sudo('python setup.py develop')

@roles('web')
def setup_staging():
    run('git clone https://github.com/samuelclay/NewsBlur.git staging')
    with cd('~/staging'):
        run('cp ../newsblur/local_settings.py local_settings.py')
        run('mkdir -p logs')
        run('touch logs/newsblur.log')
    
# ==============
# = Setup - DB =
# ==============    

def setup_db_firewall():
    sudo('ufw default deny')
    sudo('ufw allow ssh')
    sudo('ufw allow 80')
    sudo('ufw allow from 199.15.253.0/24 to any port 5432 ') # PostgreSQL
    sudo('ufw allow from 199.15.250.0/24 to any port 5432 ') # PostgreSQL
    sudo('ufw allow from 199.15.253.0/24 to any port 27017') # MongoDB
    sudo('ufw allow from 199.15.250.0/24 to any port 27017') # MongoDB
    sudo('ufw allow from 199.15.253.0/24 to any port 5672 ') # RabbitMQ
    sudo('ufw allow from 199.15.250.0/24 to any port 5672 ') # RabbitMQ
    sudo('ufw --force enable')
    
def setup_db_motd():
    put('config/motd_db.txt', '/etc/motd.tail', use_sudo=True)
    
def setup_rabbitmq():
    sudo('echo "deb http://www.rabbitmq.com/debian/ testing main" >> /etc/apt/sources.list')
    run('wget http://www.rabbitmq.com/rabbitmq-signing-key-public.asc')
    sudo('apt-key add rabbitmq-signing-key-public.asc')
    run('rm rabbitmq-signing-key-public.asc')
    sudo('apt-get update')
    sudo('apt-get install -y rabbitmq-server')
    sudo('rabbitmqctl add_user newsblur newsblur')
    sudo('rabbitmqctl add_vhost newsblurvhost')
    sudo('rabbitmqctl set_permissions -p newsblurvhost newsblur ".*" ".*" ".*"')

def setup_postgres():
    sudo('apt-get -y install postgresql-9.0 postgresql-client-9.0 postgresql-contrib-9.0 libpq-dev')

def setup_mongo():
    sudo('apt-key adv --keyserver keyserver.ubuntu.com --recv 7F0CEB10')
    # sudo('echo "deb http://downloads.mongodb.org/distros/ubuntu 10.10 10gen" >> /etc/apt/sources.list.d/10gen.list')
    sudo('echo "deb http://downloads-distro.mongodb.org/repo/debian-sysvinit dist 10gen" >> /etc/apt/sources.list')
    sudo('apt-get update')
    sudo('apt-get -y install mongodb-10gen')
    
# ================
# = Setup - Task =
# ================

def setup_task_firewall():
    sudo('ufw default deny')
    sudo('ufw allow ssh')
    sudo('ufw allow 80')
    sudo('ufw --force enable')

def setup_task_motd():
    put('config/motd_task.txt', '/etc/motd.tail', use_sudo=True)
    
def enable_celery_supervisor():
    put('config/supervisor_celeryd.conf', '/etc/supervisor/conf.d/celeryd.conf', use_sudo=True)
    
# ======
# = S3 =
# ======

if django_settings:
    try:
        ACCESS_KEY  = django_settings.S3_ACCESS_KEY
        SECRET      = django_settings.S3_SECRET
        BUCKET_NAME = django_settings.S3_BACKUP_BUCKET  # Note that you need to create this bucket first
    except:
        print " ---> You need to fix django's settings. Enter python and type `import settings`."

def save_file_in_s3(filename):
    conn   = S3Connection(ACCESS_KEY, SECRET)
    bucket = conn.get_bucket(BUCKET_NAME)
    k      = Key(bucket)
    k.key  = filename

    k.set_contents_from_filename(filename)

def get_file_from_s3(filename):
    conn   = S3Connection(ACCESS_KEY, SECRET)
    bucket = conn.get_bucket(BUCKET_NAME)
    k      = Key(bucket)
    k.key  = filename

    k.get_contents_to_filename(filename)

def list_backup_in_s3():
    conn   = S3Connection(ACCESS_KEY, SECRET)
    bucket = conn.get_bucket(BUCKET_NAME)

    for i, key in enumerate(bucket.get_all_keys()):
        print "[%s] %s" % (i, key.name)

def delete_all_backups():
    #FIXME: validate filename exists
    conn   = S3Connection(ACCESS_KEY, SECRET)
    bucket = conn.get_bucket(BUCKET_NAME)

    for i, key in enumerate(bucket.get_all_keys()):
        print "deleting %s" % (key.name)
        key.delete()