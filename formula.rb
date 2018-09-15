class ndnrtc_stream < Formula
  include Language::Python::Virtualenv

  desc "A python wrapper for ndnrtc-client for quick&easy NDN video streaming"
  homepage "https://github.com/remap/ndnrtc-stream"
  url "https://github.com/remap/ndnrtc-stream/archive/v0.0.1.tar.gz"
  sha256 "15b51d991752643c99be1437a3c08f80661693df6d01a6e9ac16066da6eed99a"

  depends_on "python3"

  resource "docopt" do
    url "https://files.pythonhosted.org/packages/a2/55/8f8cab2afd404cf578136ef2cc5dfb50baa1761b68c9da1fb1e4eed343c9/docopt-0.6.2.tar.gz"
    sha256 "49b3a825280bd66b3aa83585ef59c4a8c82f2c8a522dbe754a8bc8d08c85c491"
  end

  def install
    virtualenv_create(libexec, "python3")
    virtualenv_install_with_resources
  end

  test do
    true
  end
end
