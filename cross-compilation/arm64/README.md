# Cloud9 Cross Compilation for ARM64

## Preparation

1. Upload the following files to the Cloud9's development environment, e.g. `/home/ubuntu/environment`
   - [Dockerfile.bionic](Dockerfile.bionic)
   - [bionic-sources-arm64.yaml](bionic-sources-arm64.yaml)
   - [build_image_arm64.bash](build_image_arm64.bash)

2. In a Cloud9's bash terminal, run the following commands:

    ```bash
    sudo cp Dockerfile.bionic /opt/robomaker/cross-compilation-dockerfile/
    sudo cp bionic-sources-arm64.yaml /opt/robomaker/cross-compilation-dockerfile/
    sudo cp build_image_arm64.bash /opt/robomaker/cross-compilation-dockerfile/bin/
    ```

3. In the same bash terminal, run the following commands to build and bundle your application for ARM64:

    ```bash
    cd /opt/robomaker/cross-compilation-dockerfile/
    sudo chmod +x bin/build_image_arm64.bash
    sudo bin/build_image_arm64.bash

    cd ~/environment/[ENVIRONMENT_NAME]/robot_ws

    sudo docker run -v $(pwd):/ws -it ros-cross-compile:arm64
    cd ws

    apt update
    rosdep install --from-paths src --ignore-src -r -y

    colcon build --build-base arm64_build --install-base arm64_install
    colcon bundle --build-base arm64_build --install-base arm64_install --bundle-base arm64_bundle --apt-sources-list /opt/cross/apt-sources.yaml

    exit
    ```

    At the end of the above process, you should see the file `output.tar` under the `arm64_bundle` directory.

4. Copy `arm64_bundle/output.tar` file to an Amazon S3 bucket that AWS RoboMaker can access.

    ```bash
    aws s3 cp arm64_bundle/output.tar s3://[BUCKET_NAME]/apps/[APP_NAME].arm64.tar
    ```
