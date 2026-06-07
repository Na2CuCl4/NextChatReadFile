set -a && source .env && set +a
echo ">>> Building ${PROJECT_NAME}:v$VERSION ..."
docker build -t ${PROJECT_NAME}:v$VERSION .
echo ">>> Pushing ${PROJECT_NAME}:v$VERSION ..."
docker push ${PROJECT_NAME}:v$VERSION
echo ">>> Tagging as latest ..."
docker tag ${PROJECT_NAME}:v$VERSION ${PROJECT_NAME}:latest
echo ">>> Pushing latest ..."
docker push ${PROJECT_NAME}:latest
echo ">>> Done."
