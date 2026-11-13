// LiteTrack 自动化：接口与 UI 分阶段执行，报告目录分开，避免第二次 pytest 清掉第一次的结果。
pipeline {
    agent any

    options {
        skipDefaultCheckout(true)
        timestamps()
        timeout(time: 60, unit: 'MINUTES')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install') {
            steps {
                script {
                    if (isUnix()) {
                        sh 'python -m pip install --upgrade pip'
                        sh 'python -m pip install -r requirements.txt'
                    } else {
                        bat 'python -m pip install --upgrade pip'
                        bat 'python -m pip install -r requirements.txt'
                    }
                }
            }
        }

        stage('Run API Tests') {
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    script {
                        // 覆盖 pytest.ini 里的 alluredir，只清理接口结果目录
                        def command = 'python -m pytest testcases/api --alluredir=allure-results/api --clean-alluredir'
                        if (isUnix()) {
                            sh command
                        } else {
                            bat command
                        }
                    }
                }
            }
        }

        stage('Run UI Tests') {
            steps {
                catchError(buildResult: 'UNSTABLE', stageResult: 'FAILURE') {
                    script {
                        def command = 'python -m pytest testcases/ui --headless --alluredir=allure-results/ui --clean-alluredir'
                        if (isUnix()) {
                            sh command
                        } else {
                            bat command
                        }
                    }
                }
            }
        }

        stage('Generate Allure Report') {
            steps {
                script {
                    def command = 'allure generate allure-results/api allure-results/ui -o allure-report --clean'
                    if (isUnix()) {
                        sh command
                    } else {
                        bat command
                    }
                }
                archiveArtifacts artifacts: 'allure-report/**', allowEmptyArchive: true
            }
        }
    }

    post {
        always {
            allure includeProperties: false, results: [
                [path: 'allure-results/api'],
                [path: 'allure-results/ui']
            ]
        }
    }
}
