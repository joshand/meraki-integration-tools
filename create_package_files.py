import os
import shutil
from git import Repo


packages = ["aci", "dnac", "freenas", "general_server", "meraki", "nexus_catalog", "ucs_catalog", "catalyst_catalog", "vcenter"]
file_path = os.path.realpath(__file__).replace("create_package_files.py", "")
repo = Repo.init(file_path).git
index = Repo.init(file_path).index


for p in packages:
    print("Creating/Updating package for", p, "...")
    p_path = file_path + "packages/" + p
    zip_file = p_path + "/" + p + ".zip"
    try:
        os.remove(zip_file)
    except FileNotFoundError:
        pass

    ret = shutil.make_archive(zip_file.replace(".zip", ""), "zip", p_path)
    repo.add(ret)
    index.commit("update " + p + " package")
