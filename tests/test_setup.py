from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class DotfileSetupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "home with spaces"
        self.home.mkdir()
        self.env = dict(os.environ, HOME=str(self.home),
                        XDG_STATE_HOME=str(self.home / ".local/state"))

    def run_setup(self, *args):
        return subprocess.run(["bash", str(ROOT / "setup.sh"), "dotfiles", *args],
                              cwd=self.temporary.name, env=self.env,
                              text=True, capture_output=True, check=True)

    def test_preserves_distribution_bashrc_and_backs_up_existing_files(self):
        bashrc = self.home / ".bashrc"
        bashrc.write_text("# original distribution settings\nexport ORIGINAL=1\n")
        bashrc.chmod(0o600)
        (self.home / ".vimrc").write_text("old vim settings\n")
        self.run_setup()
        text = bashrc.read_text()
        self.assertIn("export ORIGINAL=1", text)
        self.assertEqual(text.count("# Rich configurations (managed)"), 1)
        self.assertEqual(bashrc.stat().st_mode & 0o777, 0o600)
        backups = list((self.home / ".local/state/configurations/backups").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / ".vimrc").read_text(), "old vim settings\n")
        self.assertEqual((backups[0] / ".bashrc").read_text(),
                         "# original distribution settings\nexport ORIGINAL=1\n")
        self.assertEqual(backups[0].stat().st_mode & 0o777, 0o700)
        self.assertTrue((self.home / ".vim/colors/lucius.vim").exists())

    def test_rerun_is_idempotent(self):
        self.run_setup()
        before = {path: path.read_bytes() for path in self.home.rglob("*") if path.is_file()}
        result = self.run_setup()
        after = {path: path.read_bytes() for path in self.home.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertNotIn("Copy:", result.stdout)
        self.assertFalse((self.home / ".local/state/configurations/backups").exists())

    def test_dry_run_writes_nothing(self):
        self.run_setup("--dry-run")
        self.assertEqual(list(self.home.iterdir()), [])

    def test_replaces_symlink_without_modifying_its_target(self):
        target = Path(self.temporary.name) / "external-vimrc"
        target.write_text("external settings\n")
        (self.home / ".vimrc").symlink_to(target)
        self.run_setup()
        self.assertEqual(target.read_text(), "external settings\n")
        self.assertFalse((self.home / ".vimrc").is_symlink())
        backup = next((self.home / ".local/state/configurations/backups").iterdir())
        self.assertTrue((backup / ".vimrc").is_symlink())

    def test_noninteractive_bash_has_no_side_effects(self):
        result = subprocess.run([
            "bash", "--noprofile", "--norc", "-c",
            'config=$1; set -- first second; source "$config"; printf "%s %s" "$1" "$2"',
            "test", str(ROOT / "configs/bash/.bashrc"),
        ], env=self.env, text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout, "first second")
        self.assertEqual(result.stderr, "")

    def test_baseline_dry_run_does_not_mutate_home(self):
        result = subprocess.run(["bash", str(ROOT / "setup.sh"), "--dry-run"],
                                env=self.env, text=True, capture_output=True, check=True)
        for package in ("vim", "git", "tmux", "rsync", "htop"):
            self.assertIn(package, result.stdout)
        for package in ("python3", "tailscale", "ffmpeg"):
            self.assertNotIn(package, result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_dotfiles_mode_never_installs_packages(self):
        result = self.run_setup()
        self.assertNotIn("sudo", result.stdout)
        self.assertNotIn("apt-get", result.stdout)
        self.assertNotIn("dnf", result.stdout)

    def make_checkout(self):
        checkout = Path(self.temporary.name) / "checkout with spaces"
        shutil.copytree(ROOT / "configs", checkout / "configs")
        shutil.copyfile(ROOT / "setup.sh", checkout / "setup.sh")
        (checkout / ".git").mkdir()
        return checkout

    @unittest.skipIf(os.getuid() == 0, "installer intentionally refuses root")
    def test_default_installs_only_personal_tools_and_applies_settings(self):
        for distro in ("debian", "fedora"):
            with self.subTest(distro=distro), tempfile.TemporaryDirectory() as temporary:
                checkout = Path(temporary) / "checkout"
                shutil.copytree(ROOT / "configs", checkout / "configs")
                (checkout / ".git").mkdir()
                script = checkout / "setup.sh"
                script.write_text((ROOT / "setup.sh").read_text()
                                  .replace('. /etc/os-release', '. "$SETUP_OS_RELEASE"'))
                release = Path(temporary) / "os-release"
                release.write_text(f"ID={distro}\n")
                binary = Path(temporary) / "bin"
                binary.mkdir()
                log = Path(temporary) / "commands.log"
                sudo = binary / "sudo"
                sudo.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$SETUP_COMMAND_LOG"\n')
                sudo.chmod(0o755)
                environment = dict(self.env, PATH=f"{binary}:{os.environ['PATH']}",
                                   SETUP_COMMAND_LOG=str(log), SETUP_OS_RELEASE=str(release))
                subprocess.run(["bash", str(script)], env=environment,
                               text=True, capture_output=True, check=True)
                commands = log.read_text()
                packages = next(line.split() for line in commands.splitlines() if "install" in line)
                for package in ("git", "tmux", "rsync", "htop",
                                "vim" if distro == "debian" else "vim-enhanced"):
                    self.assertIn(package, packages)
                for package in ("python3", "tailscale", "ffmpeg", "jq", "ripgrep", "unzip"):
                    self.assertNotIn(package, packages)
                self.assertTrue((self.home / ".bashrc").exists())
                self.assertTrue((self.home / ".vimrc").exists())
                self.assertTrue((self.home / ".tmux.conf").exists())

    def test_export_copies_only_managed_settings_into_checkout(self):
        checkout = self.make_checkout()
        (self.home / ".vimrc").write_text("updated vim settings\n")
        (self.home / ".tmux.conf").write_text("updated tmux settings\n")
        (self.home / ".bashrc").write_text("private distribution settings\n")
        managed = self.home / ".config/rich-configurations/bashrc"
        managed.parent.mkdir(parents=True)
        managed.write_text("updated personal Bash settings\n")
        result = subprocess.run(["bash", str(checkout / "setup.sh"), "export"],
                                env=self.env, text=True, capture_output=True, check=True)
        self.assertEqual((checkout / "configs/vim/.vimrc").read_text(), "updated vim settings\n")
        self.assertEqual((checkout / "configs/tmux/.tmux.conf").read_text(), "updated tmux settings\n")
        self.assertEqual((checkout / "configs/bash/.bashrc").read_text(), "updated personal Bash settings\n")
        self.assertEqual((self.home / ".bashrc").read_text(), "private distribution settings\n")
        self.assertNotIn("sudo", result.stdout)
        self.assertFalse((self.home / ".local/state").exists())

    def test_export_dry_run_leaves_checkout_and_home_unchanged(self):
        checkout = self.make_checkout()
        (self.home / ".vimrc").write_text("updated vim settings\n")
        before = {path: path.read_bytes() for path in Path(self.temporary.name).rglob("*")
                  if path.is_file()}
        subprocess.run(["bash", str(checkout / "setup.sh"), "export", "--dry-run"],
                       env=self.env, text=True, capture_output=True, check=True)
        after = {path: path.read_bytes() for path in Path(self.temporary.name).rglob("*")
                 if path.is_file()}
        self.assertEqual(before, after)

    def test_export_does_not_copy_the_distribution_bashrc(self):
        checkout = self.make_checkout()
        original = (checkout / "configs/bash/.bashrc").read_bytes()
        (self.home / ".bashrc").write_text("private distribution settings\n")
        subprocess.run(["bash", str(checkout / "setup.sh"), "export"],
                       env=self.env, text=True, capture_output=True, check=True)
        self.assertEqual((checkout / "configs/bash/.bashrc").read_bytes(), original)

    def test_rejects_unknown_or_conflicting_commands_without_changes(self):
        for args in (("--unknown",), ("dotfiles", "export")):
            with self.subTest(args=args):
                result = subprocess.run(["bash", str(ROOT / "setup.sh"), *args],
                                        env=self.env, text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(list(self.home.iterdir()), [])

    def test_all_scripts_have_valid_syntax(self):
        for script in ("setup.sh", "configs/bash/.bashrc"):
            subprocess.run(["bash", "-n", str(ROOT / script)], check=True)

    def test_standalone_installer_refuses_an_old_cached_checkout(self):
        downloaded = Path(self.temporary.name) / "rich-setup.sh"
        downloaded.write_bytes((ROOT / "setup.sh").read_bytes())
        cached = self.home / ".local/share/configurations"
        (cached / ".git").mkdir(parents=True)
        (cached / "configs").mkdir()
        result = subprocess.run(["bash", str(downloaded), "--dry-run"], env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not setup-ready", result.stderr)

    def test_standalone_preview_does_not_clone_or_write_files(self):
        downloaded = Path(self.temporary.name) / "rich-setup.sh"
        downloaded.write_bytes((ROOT / "setup.sh").read_bytes())
        result = subprocess.run(["bash", str(downloaded), "--dry-run"], env=self.env,
                                text=True, capture_output=True, check=True)
        self.assertIn("git clone", result.stdout)
        self.assertIn("after cloning", result.stdout)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_standalone_export_requires_a_checkout(self):
        downloaded = Path(self.temporary.name) / "rich-setup.sh"
        downloaded.write_bytes((ROOT / "setup.sh").read_bytes())
        result = subprocess.run(["bash", str(downloaded), "export"], env=self.env,
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Run export from a checkout", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
