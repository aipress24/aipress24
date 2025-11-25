# Installation of MinIO local server for S3 testing on Mac OS

Install Minio: 

```bash
brew install minio/stable/minio
```

Install CLI for minio:
```bash
brew install minio/stable/mc
```

Test:
```bash
minio --version
```

Create a local directory to store data:
```bash
mkdir -p /var/tmp/minio-data
```

In a dedicated terminal, start the Minio server:
```bash
minio server /var/tmp/minio-data --console-address ":9001"
```

(Minio will use default credential, or set environment variables
MINIO_ROOT_USER  (default:  minioadmin) and 
MINIO_ROOT_PASSWORD (default minioadmin)


Create the required bucket:
Here we use the name "s3", could also be "local" or something else.

```bash
mc alias set s3 http://127.0.0.1:9000 minioadmin minioadmin
mc mb s3/aipress24-images --region fr-paris
```

To remove bucket and data:
```bash
mc rb --force --dangerous s3   
```
