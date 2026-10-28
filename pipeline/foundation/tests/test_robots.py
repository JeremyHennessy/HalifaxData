import unittest,pathlib,hashlib
from source_policies.robots import decide
ROOT=pathlib.Path(__file__).resolve().parents[1]
class RobotsTests(unittest.TestCase):
 def d(self,rules,path='/a',agent='ExampleBot'):
  return decide(rules.encode(), 'https://example.test'+path,agent)
 def test_longest_deny(self):self.assertEqual(self.d('User-agent: *\nAllow: /\nDisallow: /a')['status'],'disallow')
 def test_longest_allow(self):self.assertEqual(self.d('User-agent: *\nDisallow: /\nAllow: /a')['status'],'allow')
 def test_tie_allow(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a\nAllow: /a')['status'],'allow')
 def test_no_first_match(self):
  a=self.d('User-agent: *\nAllow: /\nDisallow: /a');b=self.d('User-agent: *\nDisallow: /a\nAllow: /');self.assertEqual(a['status'],b['status'])
 def test_wildcard_zero(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a*b','/ab')['status'],'disallow')
 def test_wildcard_many(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a*b','/a/long/b')['status'],'disallow')
 def test_anchor_exact(self):
  self.assertEqual(self.d('User-agent: *\nDisallow: /a$','/a')['status'],'disallow');self.assertEqual(self.d('User-agent: *\nDisallow: /a$','/ab')['status'],'allow')
 def test_query_part(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a?x=1$','/a?x=1')['status'],'disallow')
 def test_case_sensitive_path(self):self.assertEqual(self.d('User-agent: *\nDisallow: /A','/a')['status'],'allow')
 def test_case_insensitive_exact_agent(self):self.assertEqual(self.d('User-agent: examplebot\nDisallow: /')['status'],'disallow')
 def test_specific_group_overrides_wildcard(self):self.assertEqual(self.d('User-agent: *\nDisallow: /\nUser-agent: ExampleBot\nAllow: /')['status'],'allow')
 def test_not_substring_agent(self):self.assertEqual(self.d('User-agent: Bot\nDisallow: /')['status'],'allow')
 def test_merge_exact_groups(self):self.assertEqual(self.d('User-agent: ExampleBot\nAllow: /b\nUser-agent: ExampleBot\nDisallow: /a')['status'],'disallow')
 def test_merge_wildcard_groups(self):self.assertEqual(self.d('User-agent: *\nAllow: /b\nUser-agent: *\nDisallow: /a')['status'],'disallow')
 def test_sitemap_does_not_break_group(self):self.assertEqual(self.d('User-agent: ExampleBot\nSitemap: https://example.test/map\nDisallow: /a')['status'],'disallow')
 def test_percent_unreserved(self):self.assertEqual(self.d('User-agent: *\nDisallow: /abc','/%61bc')['status'],'disallow')
 def test_percent_reserved_not_decoded(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a/b','/a%2Fb')['status'],'allow')
 def test_percent_case_normalized(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a%2Fb','/a%2fb')['status'],'disallow')
 def test_utf8(self):self.assertEqual(self.d('User-agent: *\nDisallow: /café','/caf%C3%A9')['status'],'disallow')
 def test_literal_star(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a%2Ab$','/a*b')['status'],'disallow')
 def test_literal_dollar(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a%24$','/a$')['status'],'disallow')
 def test_leading_wildcard_rfc_example(self):self.assertEqual(self.d('User-agent: *\nDisallow: *.gif$','/x.gif')['status'],'disallow')
 def test_google_documented_wildcard_precedence(self):self.assertEqual(self.d('User-agent: *\nAllow: /page\nDisallow: /*.htm','/page.htm')['status'],'disallow')
 def test_google_documented_equal_precedence(self):self.assertEqual(self.d('User-agent: *\nAllow: /page\nDisallow: /*.ph','/page.php5')['status'],'allow')
 def test_trailing_wildcard_equivalence_allow_tie(self):
  self.assertEqual(self.d('User-agent: *\nAllow: /fish\nDisallow: /fish*','/fish')['status'],'allow')
 def test_repeated_trailing_wildcard_cannot_inflate_allow(self):
  self.assertEqual(self.d('User-agent: *\nAllow: /fish********\nDisallow: /fish/private','/fish/private')['status'],'disallow')
 def test_terminal_wildcard_anchor_same_prefix(self):
  self.assertEqual(self.d('User-agent: *\nAllow: /fish\nDisallow: /fish*$','/fish/child')['status'],'allow')
 def test_adjacent_wildcard_canonical(self):
  self.assertEqual(self.d('User-agent: *\nAllow: /a*b\nDisallow: /a****b','/a/x/b')['status'],'allow')
 def test_invalid_escape_review(self):self.assertEqual(self.d('User-agent: *\nDisallow: /%GG')['status'],'review_required')
 def test_malformed_relative_review(self):self.assertEqual(self.d('User-agent: *\nDisallow: admin/')['status'],'review_required')
 def test_rule_before_group_review(self):self.assertEqual(self.d('Disallow: /\nUser-agent: *')['status'],'review_required')
 def test_unsupported_directive_review(self):self.assertEqual(self.d('User-agent: *\nRequest-rate: 1/10')['status'],'review_required')
 def test_unknown_encoding_review(self):self.assertEqual(decide(b'\xff','https://example.test/a','Bot')['status'],'review_required')
 def test_empty_policy(self):self.assertEqual(self.d('')['status'],'allow')
 def test_no_access_authorization(self):self.assertFalse(self.d('')['accessAuthorized']);self.assertFalse(self.d('')['transportOrExistingHoldChanged'])
 def test_retained_water(self):
  body=(ROOT/'fixtures/robots/halifax-water.txt').read_bytes();self.assertEqual(hashlib.sha256(body).hexdigest(),'773fb8d35bb9a39d35335ee6db8dc5c912d2aacbfb823152d9c61cd647dd902d');r=decide(body,'https://halifaxwater.ca/sites/default/files/2024-10/Public%20Package%20-%20September%2026%2C%202024.pdf','HalifaxDataResearch');self.assertEqual(r['status'],'allow')
 def test_retained_nshealth(self):
  body=(ROOT/'fixtures/robots/nshealth.txt').read_bytes();self.assertEqual(hashlib.sha256(body).hexdigest(),'8e8cb58d810473a52cce903be5ffb73d948eef981bbd101cffbf8dc2c02fcf4e');r=decide(body,'https://www.nshealth.ca/sites/default/files/documents/26%20-%20NSH%20FY26%20Financial%20Statements%20-%20FINAL.pdf','HalifaxDataResearch');self.assertEqual(r['status'],'allow')
 def test_real_policy_protected_area_stays_denied(self):
  for name in ('halifax-water','nshealth'):
   r=decide((ROOT/'fixtures/robots'/f'{name}.txt').read_bytes(),'https://example.test/admin/secret','HalifaxDataResearch');self.assertEqual(r['status'],'disallow')
 def test_real_policy_css_specific_allow(self):
  r=decide((ROOT/'fixtures/robots/nshealth.txt').read_bytes(),'https://www.nshealth.ca/core/example.css','HalifaxDataResearch');self.assertEqual(r['status'],'allow')
 def test_matching_budget_fail_closed(self):
  from unittest.mock import patch
  with patch('source_policies.robots.MAX_STEPS',1):self.assertEqual(self.d('User-agent: *\nDisallow: /a*')['status'],'review_required')
 def test_url_control_not_silently_removed(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a','/\na')['status'],'review_required')
 def test_path_quote_normalization(self):self.assertEqual(self.d('User-agent: *\nDisallow: /a%22b','/a"b')['status'],'disallow')
 def test_empty_pattern_no_restriction(self):self.assertEqual(self.d('User-agent: *\nDisallow:')['status'],'allow')
 def test_crawl_delay_group_scope(self):
  r=self.d('User-agent: *\nCrawl-delay: 9\nUser-agent: ExampleBot\nCrawl-delay: 2\nAllow: /');self.assertEqual(r['crawlDelaySeconds'],2)
 def test_full_header_not_product_token(self):self.assertEqual(self.d('',agent='ExampleBot/1.0')['status'],'review_required')
 def test_bom_comments_crlf(self):self.assertEqual(self.d('\ufeffUser-agent: *\r\nDisallow: /a # note\r\n')['status'],'disallow')
 def test_oversize_policy_hold(self):self.assertEqual(decide(b'#'*512001,'https://example.test/a','Bot')['status'],'review_required')
if __name__=='__main__':unittest.main()
