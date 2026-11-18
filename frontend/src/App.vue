<template>
  <main>
    <header>
      <h1>售后工单工作台</h1>
      <el-tag type="info">模拟数据</el-tag>
    </header>
    <el-card>
      <h2>工单处理</h2>
      <el-alert title="工单功能尚未开放" type="info" :closable="false" />
      <p>后续将在这里创建工单、查看调查过程并处理人工待办。</p>
    </el-card>
  </main>
</template>

<style scoped>
main { max-width: 1080px; margin: 48px auto; padding: 0 24px; color: #243040; font-family: system-ui, sans-serif; }
header { display: flex; align-items: center; gap: 16px; margin-bottom: 24px; }
h1 { font-size: 26px; }
h2 { margin-top: 0; font-size: 20px; }
p { line-height: 1.7; color: #586579; }
</style>
