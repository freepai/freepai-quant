# Docker container for working with neural networks ([Anaconda3](https://www.anaconda.com/download/), [TensorFlow (CPU)](https://www.tensorflow.org/install/), [Keras](https://keras.io/#installation))
Published at [DockerHub](https://hub.docker.com/r/taivokasper/docker-neural-net-env/tags/).

## Instructions

* Run the environment (replace `$local_notebook_path` with local jupyter notebook path)
    ```bash
    docker run -it --rm -p 8888:8888 -v $local_notebook_path:/notebook taivokasper/neural-net-env:latest
    ```
* Navigate to [http://localhost:8888](http://localhost:8888)
    If asked about credentials then look at the terminal output.
