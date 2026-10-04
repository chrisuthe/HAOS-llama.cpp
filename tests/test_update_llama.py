import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent
spec = importlib.util.spec_from_file_location("update_llama", ROOT / "scripts/update_llama.py")
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)

OLD = "sha256:" + "a" * 64
NEW = "sha256:" + "b" * 64
DOCKERFILE = f"# comment\nFROM ghcr.io/ggml-org/llama.cpp:server-vulkan-v0.5.0@{OLD}\n\nCOPY rootfs/ /\n"


class Repin(unittest.TestCase):
    def test_reads_the_current_tag(self):
        self.assertEqual(update.current_tag(DOCKERFILE), "v0.5.0")

    def test_replaces_tag_and_digest_only(self):
        self.assertEqual(
            update.repin(DOCKERFILE, "v0.6.0", NEW),
            DOCKERFILE.replace("v0.5.0", "v0.6.0").replace(OLD, NEW),
        )

    def test_missing_from_line_is_an_error(self):
        with self.assertRaises(SystemExit):
            update.current_tag("FROM ubuntu:26.04\n")

    def test_the_real_dockerfile_matches(self):
        # The updater is useless if the Dockerfile drifts from this shape.
        self.assertRegex(update.current_tag(update.DOCKERFILE.read_text()), r"^v\d+\.\d+\.\d+$")


class Version(unittest.TestCase):
    def test_bumps_the_patch(self):
        config, version = update.bump_patch('name: x\nversion: "0.1.9"\nslug: y\n')
        self.assertEqual(version, "0.1.10")
        self.assertEqual(config, 'name: x\nversion: "0.1.10"\nslug: y\n')

    def test_the_real_config_matches(self):
        update.bump_patch(update.CONFIG.read_text())


class Changelog(unittest.TestCase):
    def test_new_entry_goes_above_the_previous_one(self):
        before = "# Changelog\n\n## 0.1.0\n\n- First version, on llama.cpp v0.5.0.\n"
        self.assertEqual(
            update.add_changelog_entry(before, "0.1.1", "v0.6.0"),
            "# Changelog\n\n## 0.1.1\n\n- Update llama.cpp to v0.6.0.\n\n"
            "## 0.1.0\n\n- First version, on llama.cpp v0.5.0.\n",
        )

    def test_empty_changelog(self):
        self.assertEqual(
            update.add_changelog_entry("# Changelog\n", "0.1.1", "v0.6.0"),
            "# Changelog\n\n## 0.1.1\n\n- Update llama.cpp to v0.6.0.\n",
        )


if __name__ == "__main__":
    unittest.main()
