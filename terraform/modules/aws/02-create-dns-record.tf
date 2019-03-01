resource "aws_route53_record" "dns_record" {
  zone_id = "${data.aws_route53_zone.selected.zone_id}"
  name    = "${var.dns_hostname}.${data.aws_route53_zone.selected.name}"
  type    = "A"
  ttl     = "300"
  records = ["${var.ips}"]
}
