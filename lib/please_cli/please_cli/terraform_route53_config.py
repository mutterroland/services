# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from __future__ import absolute_import
import click
import please_cli.config

HEROKU_COMMENT = '##Heroku {channel} app cnames##'


def echo_heroku_comment(channel):
    line = '#' * len(HEROKU_COMMENT.format(channel=channel))
    click.echo(line)
    click.echo(HEROKU_COMMENT.format(channel=channel))
    click.echo(line)


HEADER = '''

######################################################################
#                                                                    #
# IMPORTANT: mozilla-releng.net resources were generated, do not     #
#            change them manually!                                   #
#                                                                    #
#     https://docs.mozilla-releng.net/deploy/configure-dns.html      #
#                                                                    #
######################################################################

resource "aws_route53_zone" "mozilla-releng" {
    name = "mozilla-releng.net."
}

# A special root alias that points to www.mozilla-releng.net
resource "aws_route53_record" "root-alias" {
    zone_id = "${aws_route53_zone.mozilla-releng.zone_id}"
    name = "mozilla-releng.net"
    type = "A"

    alias {
        name = "www.mozilla-releng.net"
        zone_id = "${aws_route53_zone.mozilla-releng.zone_id}"
        evaluate_target_health = false
    }
}

resource "aws_route53_record" "heroku-coalease-cname" {
    zone_id = "${aws_route53_zone.mozilla-releng.zone_id}"
    name = "coalesce.mozilla-releng.net"
    type = "CNAME"
    ttl = "180"
    records = ["oita-54541.herokussl.com"]
}
'''

HEROKU_TEMPLATE = '''
resource "aws_route53_record" "%(name)s" {
    zone_id = "${aws_route53_zone.mozilla-releng.zone_id}"
    name = "%(domain)s"
    type = "CNAME"
    ttl = "180"
    records = ["%(dns)s"]
}
'''
S3_TEMPLATE = '''
############################
## CloudFront CDN aliases ##
############################

variable "cloudfront_alias" {
    default = [%(alias)s]
}

# Cloudfront Alias Targets
# In the future, these may be sourced directly from terraform cloudfront resources
# should we decide to manage cloudfronts in terraform
variable "cloudfront_alias_domain" {
    type = "map"
    default = {%(alias_targets)s}
}

# A (Alias) records for cloudfront apps
resource "aws_route53_record" "cloudfront-alias" {
    zone_id = "${aws_route53_zone.mozilla-releng.zone_id}"
    name = "${element(var.cloudfront_alias, count.index)}.mozilla-releng.net"
    type = "A"
    count = "${length(var.cloudfront_alias)}"

    alias {
        name = "${var.cloudfront_alias_domain[element(var.cloudfront_alias, count.index)]}.cloudfront.net."
        zone_id = "Z2FDTNDATAQYW2"
        evaluate_target_health = false
    }
}

# A special root alias that points to www.mozilla-releng.net
resource "aws_route53_record" "root-alias" {
    zone_id = "${aws_route53_zone.mozilla-releng.zone_id}"
    name = "mozilla-releng.net"
    type = "A"

    alias {
        name = "www.mozilla-releng.net"
        zone_id = "${aws_route53_zone.mozilla-releng.zone_id}"
        evaluate_target_health = false
    }
}
'''


def to_route53_name(project_id, channel):
    channel_short = ''
    if channel == 'production':
        channel_short = 'prod'
    elif channel == 'staging':
        channel_short = 'stage'
    elif channel == 'testing':
        channel_short = 'test'

    project_name = project_id
    if 'releng-' in project_id:
        project_name = project_name[7:]
    elif 'shipit-' in project_id:
        project_name = project_name[7:] + '-shipit'

    return 'heroku-%s-cname-%s' % (project_name,channel_short)


@click.command()
@click.option(
    '--channel',
    type=click.Choice(please_cli.config.CHANNELS),
    default=None,
    )
def cmd(channel):
    HEROKU_RELENG = dict()
    HEROKU_SHIPIT = dict()
    S3 = []

    if channel is None:
        channels = please_cli.config.CHANNELS
    else:
        channels = [channel]

    click.echo(HEADER)

    for project_id in sorted(please_cli.config.PROJECTS_CONFIG.keys()):

        project = please_cli.config.PROJECTS_CONFIG[project_id].get('deploy_options')
        project_target = please_cli.config.PROJECTS_CONFIG[project_id].get('deploy')

        if project:

            for channel in sorted(channels):

                if channel not in project or \
                       'url' not in project[channel] or \
                       'dns' not in project[channel]:
                    continue

                if 'dns_url' in project[channel]:
                    domain = project[channel]['dns_url']
                else:
                    domain = project[channel]['url']
                    domain = domain.lstrip('https')
                    domain = domain.lstrip('http')
                    domain = domain.lstrip('://')


                if project_target == 'HEROKU'
                    if project_id.startswith('releng-'):
                        HEROKU_RELENG.setdefaults(channel, [])
                        HEROKU_RELENG[channel].append(dict(
                            name=to_route53_name(project_id, channel),
                            domain=domain,
                            dns=project[channel]['dns'],
                        ))
                    if project_id.startswith('shipit-'):
                        HEROKU_SHIPIT.setdefaults(channel, [])
                        HEROKU_SHIPIT[channel].append(dict(
                            name=to_route53_name(project_id, channel),
                            domain=domain,
                            dns=project[channel]['dns'],
                        ))

                if project_target == 'S3':
                    S3.append(dict(
                        name=to_route53_name(project_id, channel),
                        domain=domain,
                        dns=project[channel]['dns'],
                    ))


    for channel in please_cli.config.CHANNELS:
        echo_heroku_comment(channel)
        for item in HEROKU_RELENG[channels]:
            click.echo(HEROKU_TEMPLATE % item)

    for channel in please_cli.config.CHANNELS:
        echo_heroku_comment('shipit ' + channel)
        for item in HEROKU_SHIPIT[channels]:
            click.echo(HEROKU_TEMPLATE % item)
