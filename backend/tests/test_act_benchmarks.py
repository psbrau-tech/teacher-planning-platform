from app.act_benchmarks import parse_act_benchmarks_html


def test_act_benchmark_parser_preserves_public_first_party_values() -> None:
    html = """
    <html><body>
      <table>
        <tr><td>English</td><td>English Composition I</td><td>18</td></tr>
        <tr><td>Mathematics</td><td>College Algebra</td><td>22</td></tr>
        <tr><td>Reading</td><td>American History, Other History, Psychology, Sociology,
        Political Science, Economics</td><td>22</td></tr>
        <tr><td>Science</td><td>Biology</td><td>23</td></tr>
        <tr><td>STEM</td><td>Calculus, Chemistry, Biology, Physics, Engineering</td><td>26</td></tr>
        <tr><td>ELA</td><td>English Composition I, American History, Other History,
        Psychology, Sociology, Political Science, Economics</td><td>20</td></tr>
      </table>
    </body></html>
    """
    parsed = parse_act_benchmarks_html(html)
    assert parsed.parser_version == "act-public-benchmarks-html-v1"
    assert [(item.domain, item.benchmark_score) for item in parsed.benchmarks] == [
        ("English", 18),
        ("Mathematics", 22),
        ("Reading", 22),
        ("Science", 23),
        ("STEM", 26),
        ("ELA", 20),
    ]
    assert len(parsed.source_sha256) == 64
    assert len(parsed.normalized_sha256) == 64
