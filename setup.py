import setuptools

setuptools.setup(
        name="distant-rec",
        version="0.1",
        author="Antmicro",
        author_email="contact@antmicro.com",
        description="REAPI client",
        url="https://github.com/antmicro",
        packages=["distantrec"],
        python_requires='>=3.6',
        entry_points={
            "console_scripts":["raclient = distantrec.raclient:main",
                "dep2yaml = distantrec.dep2yaml:main",
                "vtr2yaml = distantrec.vtr2yaml:main", ]
            },
        install_requires=["buildgrid @ git+https://github.com/antmicro/buildgrid",
            "grpcio", "pyyaml", "google-auth", "protobuf", "requests", "parse"],
        )
