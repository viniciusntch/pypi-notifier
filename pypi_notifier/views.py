from flask import render_template, request, redirect, url_for, g, abort

from pypi_notifier.extensions import db
from pypi_notifier.models import Repo


def register_views(app):

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/robots.txt')
    def robots_txt():
        return 'User-agent: *\nAllow: /'

    @app.route('/select-email', methods=['GET', 'POST'])
    def select_email():
        emails = g.user.get_emails_from_github()
        if request.method == 'POST':
            selected = request.form['email']
            if selected not in [e['email'] for e in emails]:
                abort(400)

            g.user.email = selected
            db.session.commit()
            return redirect(url_for('get_repos'))
        return render_template("select-email.html", emails=emails)

    @app.route('/repos')
    def get_repos():
        repos = g.user.get_repos_from_github()
        selected_ids = [r.github_id for r in g.user.repos]
        for repo in repos:
            repo['checked'] = (repo['id'] in selected_ids)
        return render_template('repos.html', repos=repos)

    @app.route('/repos', methods=['POST'])
    def post_repos():
        # Add selected repos
        for name, github_id in request.form.items():
            github_id = int(github_id)
            repo = Repo.query.filter(
                Repo.github_id == github_id,
                Repo.user_id == g.user.id).first()
            if repo is None:
                repo = Repo(github_id, g.user)
            repo.name = name
            db.session.add(repo)

        # Remove unselected repos
        ids = set(map(int, request.form.values()))
        for repo in g.user.repos:
            if repo.github_id not in ids:
                db.session.delete(repo)

        db.session.commit()
        return redirect(url_for('done'))

    @app.route('/done')
    def done():
        reqs = g.user.get_outdated_requirements()
        return render_template('done.html', reqs=reqs)

    @app.route('/unsubscribe', methods=['GET', 'POST'])
    def unsubscribe():
        if request.method == 'POST':
            if request.form['confirm'] == 'yes':
                if g.user:
                    db.session.delete(g.user)
                    db.session.commit()
                return render_template('unsubscribed.html')
            else:
                return redirect(url_for('index'))
        return render_template('unsubscribe-confirm.html')
