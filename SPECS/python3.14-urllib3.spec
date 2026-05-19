## START: Set by rpmautospec
## (rpmautospec version 0.8.3)
## RPMAUTOSPEC: autorelease, autochangelog
%define autorelease(e:s:pb:n) %{?-p:0.}%{lua:
    release_number = 1;
    base_release_number = tonumber(rpm.expand("%{?-b*}%{!?-b:1}"));
    print(release_number + base_release_number - 1);
}%{?-e:.%{-e*}}%{?-s:.%{-s*}}%{!?-n:%{?dist}}
## END: Set by rpmautospec

%global python3_pkgversion 3.14

# When bootstrapping Python, we cannot test this yet
# RHEL does not include the test dependencies and the dependencies for extras
%bcond tests %{undefined rhel}
%bcond extras %[%{undefined rhel} || %{defined eln}]
%bcond extradeps %{undefined rhel}

Name:           python%{python3_pkgversion}-urllib3
Version:        2.6.3
Release:        %autorelease
Summary:        HTTP library with thread-safe connection pooling, file post, and more

# SPDX
License:        MIT
URL:            https://github.com/urllib3/urllib3
Source0:        %{url}/archive/%{version}/urllib3-%{version}.tar.gz

# Replace hatchling build backend with setuptools
Patch:          Replace-hatchling-with-setuptools-build-backend.patch

# A special forked copy of Hypercorn is required for testing. We asked about
# the possiblility of using a released version in the future in:
#   Path toward testing with a released version of hypercorn?
#   https://github.com/urllib3/urllib3/3334
# Upstream would like to get the necessary changes merged into Hypercorn, but
# explained clearly why the forked copy is needed for now.
#
# Note that tool.uv.sources.hypercorn in pyproject.toml references the
# urllib3-changes branch of https://github.com/urllib3/hypercorn/, and we
# should use the latest commit from that branch, but we package using a commit
# hash for reproducibility.
#
# We do not need to treat this as a bundled dependency because it is not
# installed in the buildroot or otherwise included in any of the binary RPMs.
%global hypercorn_url https://github.com/urllib3/hypercorn
%global hypercorn_commit d1719f8c1570cbd8e6a3719ffdb14a4d72880abb
Source1:        %{hypercorn_url}/archive/%{hypercorn_commit}/hypercorn-%{hypercorn_commit}.tar.gz

BuildArch:      noarch

BuildRequires:  python%{python3_pkgversion}-devel
# The conditional is important: we benefit from tomcli for editing dependency
# groups, but we do not want it when bootstrapping or in RHEL.
%if %{with tests}
BuildRequires:  tomcli
%endif

BuildRequires:  ca-certificates
Requires:       ca-certificates

# There has historically been a manual hard dependency on python3-idna.
BuildRequires:  %{py3_dist idna}
Requires:       %{py3_dist idna}

%if %{with extradeps}
# There has historically been a manual hard dependency on python3-pysocks;
# since bringing it in is the sole function of python3-urllib3+socks,
# we recommend it, so it is installed by default.
Recommends:     python%{python3_pkgversion}-urllib3+socks
%endif

%description
urllib3 is a powerful, user-friendly HTTP client for Python. urllib3 brings
many critical features that are missing from the Python standard libraries:

  • Thread safety.
  • Connection pooling.
  • Client-side SSL/TLS verification.
  • File uploads with multipart encoding.
  • Helpers for retrying requests and dealing with HTTP redirects.
  • Support for gzip, deflate, brotli, and zstd encoding.
  • Proxy support for HTTP and SOCKS.
  • 100% test coverage.

%if %{with extras}
%pyproject_extras_subpkg -n python%{python3_pkgversion}-urllib3 brotli zstd socks h2
%endif


%prep
%autosetup -n urllib3-%{version}
%setup -q -n urllib3-%{version} -T -D -b 1

# Make sure that the RECENT_DATE value doesn't get too far behind what the current date is.
# RECENT_DATE must not be older that 2 years from the build time, or else test_recent_date
# (from test/test_connection.py) would fail. However, it shouldn't be to close to the build time either,
# since a user's system time could be set to a little in the past from what build time is (because of timezones,
# corner cases, etc). As stated in the comment in src/urllib3/connection.py:
#   When updating RECENT_DATE, move it to within two years of the current date,
#   and not less than 6 months ago.
#   Example: if Today is 2018-01-01, then RECENT_DATE should be any date on or
#   after 2016-01-01 (today - 2 years) AND before 2017-07-01 (today - 6 months)
# There is also a test_ssl_wrong_system_time test (from test/with_dummyserver/test_https.py) that tests if
# user's system time isn't set as too far in the past, because it could lead to SSL verification errors.
# That is why we need RECENT_DATE to be set at most 2 years ago (or else test_ssl_wrong_system_time would
# result in false positive), but before at least 6 month ago (so this test could tolerate user's system time being
# set to some time in the past, but not to far away from the present).
# Next few lines update RECENT_DATE dynamically.
recent_date=$(date --date "7 month ago" +"%Y, %_m, %_d")
sed -i "s/^RECENT_DATE = datetime.date(.*)/RECENT_DATE = datetime.date($recent_date)/" src/urllib3/connection.py

%if %{with tests}
# Possible improvements to dependency groups
# https://github.com/urllib3/urllib3/issues/3594
# Adjust the contents of the "dev" dependency group by removing:
remove_from_dev() {
  tomcli set pyproject.toml lists delitem 'dependency-groups.dev' "($1)\b.*"
}
#   - Linters, coverage tools, profilers, etc.:
#     https://docs.fedoraproject.org/en-US/packaging-guidelines/Python/#_linters
remove_from_dev 'coverage|pytest-memray'
#   - Dependencies for maintainer tasks
remove_from_dev 'build|towncrier'
#   - Dependencies that are not packaged and not strictly required
remove_from_dev 'pytest-socket'
#   - Hypercorn, because we have a special forked version we must use for
#     testing instead, so we do not want to generate a dependency on the system
#     copy. Note that the system copy is still an indirect dependency via quart
#     and quart-trio.
remove_from_dev 'hypercorn'

# Remove all version bounds for test dependencies. We must attempt to make do
# with what we have. (This also removes any python version or platform
# constraints, which is currently fine, but could theoretically cause trouble
# in the future. We’ll cross that bridge if we ever arrive at it.)
tomcli set pyproject.toml lists replace --type regex_search \
    'dependency-groups.dev' '[>=]=.*' ''
%endif


%generate_buildrequires
export SETUPTOOLS_SCM_PRETEND_VERSION='%{version}'
# Generate BR’s from packaged extras even when tests are disabled, to ensure
# the extras metapackages are installable if the build succeeds.
%pyproject_buildrequires %{?with_extradeps:-x brotli,zstd,socks,h2} %{?with_tests:-g dev}


%build
export SETUPTOOLS_SCM_PRETEND_VERSION='%{version}'
%pyproject_wheel


%install
%pyproject_install

%pyproject_save_files -l urllib3


%check
# urllib3.contrib.socks requires urllib3[socks]
#
# urllib3.contrib.emscripten is “special” (import js will fail)
# urllib3.contrib.ntlmpool is deprecated and requires ntlm
# urllib3.contrib.securetransport is macOS only
# urllib3.contrib.pyopenssl requires pyOpenSSL
%{pyproject_check_import %{!?with_extradeps:-e urllib3.contrib.socks -e urllib3.http2*}
                         -e urllib3.contrib.emscripten*
                         -e urllib3.contrib.ntlmpool
                         -e urllib3.contrib.securetransport
                         -e urllib3.contrib.pyopenssl}

# Increase the “long timeout” for slower environments; as of this writing, it
# is increased from 0.1 to 0.5 second.
export CI=1
# Interpose the special forked copy of Hypercorn.
hypercorndir="${PWD}/../hypercorn-%{hypercorn_commit}/src"
export PYTHONPATH="${hypercorndir}:%{buildroot}%{python3_sitelib}"

%if %{with tests}
# This test still times out sometimes, especially on certain architectures,
# even when we export the CI environment variable to increase timeouts.
k="${k-}${k+ and }not (TestHTTPProxyManager and test_tunneling_proxy_request_timeout[https-https])"

%pytest -v -rs ${ignore-} -k "${k-}"
%pytest -v -rs ${ignore-} -k "${k-}" --integration
%endif


%files -n python%{python3_pkgversion}-urllib3 -f %{pyproject_files}
%doc CHANGES.rst README.md


%changelog
## START: Generated by rpmautospec
* Tue Jan 27 2026 Benjamin A. Beasley <code@musicinmybrain.net> - 2.6.3-1
- Update to 2.6.3
- Fixes CVE-2026-21441 / GHSA-38jv-5279-wg99

* Tue Jan 27 2026 Benjamin A. Beasley <code@musicinmybrain.net> - 2.6.2-1
- Update to 2.6.2

* Tue Jan 27 2026 Benjamin A. Beasley <code@musicinmybrain.net> - 2.6.1-1
- Update to 2.6.1
- Fixes CVE-2025-66471 / GHSA-2xpw-w6gg-jr37
- Fixes CVE-2025-66418 / GHSA-gm62-xv2j-4w53

* Fri Nov 28 2025 Lukáš Zachar <lzachar@redhat.com> - 2.5.0-3
- Add gating

* Fri Nov 28 2025 Tomáš Hrnčiar <thrnciar@redhat.com> - 2.5.0-2
- Convert from Fedora for the Python 3.14 stack in RHEL

* Fri Nov 28 2025 Tomáš Hrnčiar <thrnciar@redhat.com> - 2.5.0-1
- RHEL: Rename SPEC to python3.14-urllib3.spec
## END: Generated by rpmautospec
